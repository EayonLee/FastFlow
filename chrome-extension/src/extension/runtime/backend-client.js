import {
  FASTFLOW_HTTP_REQUEST,
  FASTFLOW_HTTP_RESPONSE,
  FASTFLOW_STREAM_CANCEL,
  FASTFLOW_STREAM_CANCELLED,
  FASTFLOW_STREAM_CLOSE,
  FASTFLOW_STREAM_ERROR,
  FASTFLOW_STREAM_EVENT,
  FASTFLOW_STREAM_OPEN,
  FASTFLOW_STREAM_PORT
} from './backend-protocol.js'

const BACKGROUND_RETRY_DELAY_MS = 150
const BACKGROUND_UNAVAILABLE_MESSAGE =
  '扩展后台 service worker 未就绪，请在 chrome://extensions 中重新加载 FastFlow 扩展后重试'
const STREAM_DISCONNECTED_MESSAGE = '流式连接中断，请重试'

/**
 * 检查当前运行环境是否具备扩展运行时。
 *
 * 说明：
 * - popup、content script 都依赖 `chrome.runtime` 与后台 service worker 通信。
 * - 如果这里不可用，说明代码跑在了错误上下文，不应继续请求后端。
 */
function ensureChromeRuntime() {
  if (globalThis.chrome?.runtime) return
  throw new Error('Chrome runtime 不可用，无法请求后台服务')
}

/**
 * 将请求体序列化成后台可直接透传给 fetch 的格式。
 *
 * 规则：
 * - JSON 请求体统一转字符串
 * - 其他类型保持原样，由调用方自己保证正确性
 */
function serializeBody(body, headers = {}) {
  if (body == null) return undefined
  if (typeof body === 'string') return body

  const contentType = String(headers['Content-Type'] || headers['content-type'] || '')
  if (contentType.includes('application/json')) {
    return JSON.stringify(body)
  }

  return body
}

/**
 * 统一读取 Chrome runtime 的错误上下文，避免调用层到处判断 `lastError`。
 */
function buildRuntimeError(fallbackMessage) {
  const runtimeError = chrome.runtime?.lastError
  return new Error(runtimeError?.message || fallbackMessage)
}

function isMissingReceiverError(error) {
  const message = String(error?.message || '')
  return message.includes('Receiving end does not exist')
}

function buildBackgroundUnavailableError(rawMessage) {
  const error = new Error(BACKGROUND_UNAVAILABLE_MESSAGE)
  error.code = 'FASTFLOW_BACKGROUND_UNAVAILABLE'
  error.rawMessage = rawMessage
  return error
}

function wait(ms) {
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms))
}

async function sendRuntimeMessage(message, { retryOnMissingReceiver = false } = {}) {
  let retried = false

  while (true) {
    try {
      return await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(message, (response) => {
          if (chrome.runtime?.lastError) {
            reject(buildRuntimeError('后台服务请求失败'))
            return
          }
          resolve(response)
        })
      })
    } catch (error) {
      if (retryOnMissingReceiver && !retried && isMissingReceiverError(error)) {
        retried = true
        await wait(BACKGROUND_RETRY_DELAY_MS)
        continue
      }
      if (isMissingReceiverError(error)) {
        throw buildBackgroundUnavailableError(error.message)
      }
      throw error
    }
  }
}

/**
 * 页面侧唯一的后端客户端。
 *
 * 说明：
 * - 这里不直接发网络请求，只做消息转发。
 * - 真正的 HTTP / SSE 请求全部由 service worker 执行。
 */
export const backendClient = {
  async request({ service, path, method = 'GET', headers = {}, body, timeoutMs }) {
    ensureChromeRuntime()

    const payload = {
      service,
      path,
      method,
      headers,
      body: serializeBody(body, headers),
      timeoutMs
    }

    const response = await sendRuntimeMessage(
      {
        type: FASTFLOW_HTTP_REQUEST,
        payload
      },
      { retryOnMissingReceiver: true }
    )

    if (!response || response.type !== FASTFLOW_HTTP_RESPONSE) {
      throw new Error('后台服务返回了未知响应')
    }

    return response.payload
  },

  stream({ service, path, method = 'POST', headers = {}, body, onEvent, onComplete, onError }) {
    ensureChromeRuntime()

    // 流式请求需要长期保持通道，因此改用 Port，而不是一次性 sendMessage。
    let port = null
    let isClosed = false
    let isCancelling = false

    const close = () => {
      if (isClosed) return
      isClosed = true
      port?.disconnect()
    }

    const cancel = () => {
      if (isClosed || isCancelling) return
      isCancelling = true
      try {
        port?.postMessage({ type: FASTFLOW_STREAM_CANCEL })
      } catch {
        isClosed = true
        onError?.(new Error('取消请求发送失败，请重试'))
        port?.disconnect()
      }
    }

    try {
      port = chrome.runtime.connect({ name: FASTFLOW_STREAM_PORT })
    } catch (error) {
      isClosed = true
      const normalizedError =
        isMissingReceiverError(error)
          ? buildBackgroundUnavailableError(error.message)
          : error instanceof Error
            ? error
            : new Error('扩展后台服务不可用')
      onError?.(normalizedError)
      return { close, cancel }
    }

    port.onMessage.addListener((message) => {
      if (!message) return

      if (message.type === FASTFLOW_STREAM_EVENT) {
        onEvent?.(message.payload)
        return
      }

      if (message.type === FASTFLOW_STREAM_CANCELLED) {
        isClosed = true
        onComplete?.({
          cancelled: true,
          cancelStatus: String(message?.payload?.status || '').trim() || 'unknown',
          cancelAccepted: Boolean(message?.payload?.accepted),
          cancelPayload: message?.payload || null,
        })
        port.disconnect()
        return
      }

      if (message.type === FASTFLOW_STREAM_CLOSE) {
        isClosed = true
        onComplete?.(message.payload || null)
        port.disconnect()
        return
      }

      if (message.type === FASTFLOW_STREAM_ERROR) {
        isClosed = true
        onError?.(new Error(message.error || '流式请求失败'))
        port.disconnect()
      }
    })

    port.onDisconnect.addListener(() => {
      if (isClosed) return
      isClosed = true
      onError?.(
        new Error(isCancelling ? '取消流程中断：后台连接已断开' : STREAM_DISCONNECTED_MESSAGE)
      )
    })

    try {
      port.postMessage({
        type: FASTFLOW_STREAM_OPEN,
        payload: {
          service,
          path,
          method,
          headers,
          body: serializeBody(body, headers)
        }
      })
    } catch (error) {
      if (!isClosed) {
        isClosed = true
        onError?.(
          isMissingReceiverError(error)
            ? buildBackgroundUnavailableError(error.message)
            : error instanceof Error
              ? error
              : new Error('扩展后台服务不可用')
        )
      }
    }

    return { close, cancel }
  }
}

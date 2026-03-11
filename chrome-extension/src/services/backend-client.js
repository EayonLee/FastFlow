import {
  FASTFLOW_HTTP_REQUEST,
  FASTFLOW_HTTP_RESPONSE,
  FASTFLOW_STREAM_CLOSE,
  FASTFLOW_STREAM_ERROR,
  FASTFLOW_STREAM_EVENT,
  FASTFLOW_STREAM_OPEN,
  FASTFLOW_STREAM_PORT
} from './backend-protocol.js'

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

    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        {
          type: FASTFLOW_HTTP_REQUEST,
          payload
        },
        (message) => {
          if (chrome.runtime?.lastError) {
            reject(buildRuntimeError('后台服务请求失败'))
            return
          }
          resolve(message)
        }
      )
    })

    if (!response || response.type !== FASTFLOW_HTTP_RESPONSE) {
      throw new Error('后台服务返回了未知响应')
    }

    return response.payload
  },

  stream({ service, path, method = 'POST', headers = {}, body, onEvent, onComplete, onError, timeoutMs }) {
    ensureChromeRuntime()

    // 流式请求需要长期保持通道，因此改用 Port，而不是一次性 sendMessage。
    const port = chrome.runtime.connect({ name: FASTFLOW_STREAM_PORT })
    let isClosed = false

    const close = () => {
      if (isClosed) return
      isClosed = true
      port.disconnect()
    }

    port.onMessage.addListener((message) => {
      if (!message) return

      if (message.type === FASTFLOW_STREAM_EVENT) {
        onEvent?.(message.payload)
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
      if (chrome.runtime?.lastError) {
        onError?.(buildRuntimeError('后台流式服务已断开'))
      }
    })

    port.postMessage({
      type: FASTFLOW_STREAM_OPEN,
      payload: {
        service,
        path,
        method,
        headers,
        body: serializeBody(body, headers),
        timeoutMs
      }
    })

    return { close }
  }
}

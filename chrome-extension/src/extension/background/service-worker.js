import { createParser } from 'eventsource-parser'

import { runtimeConfig } from '@/extension/config/runtime'
import {
  FASTFLOW_HTTP_REQUEST,
  FASTFLOW_HTTP_RESPONSE,
  FASTFLOW_STREAM_CLOSE,
  FASTFLOW_STREAM_ERROR,
  FASTFLOW_STREAM_EVENT,
  FASTFLOW_STREAM_OPEN,
  FASTFLOW_STREAM_PORT
} from '@/extension/runtime/backend-protocol.js'

/**
 * Chrome 插件后台网络层。
 *
 * 职责边界：
 * - 这是插件唯一允许直接访问 API / Nexus 的地方。
 * - popup、chatbox、content script 只允许通过 runtime message / port 调用这里。
 * - 固定后端地址来自共享配置，不允许根据页面地址动态推导。
 */
const DEFAULT_HTTP_TIMEOUT_MS = 30 * 1000
const SERVICE_BASE_URL = {
  api: runtimeConfig.apiBaseUrl,
  nexus: runtimeConfig.nexusBaseUrl
}
let backgroundInitialized = false

/**
 * 将 service + path 组装成最终请求 URL。
 *
 * 这里强制要求 path 以 `/` 开头，避免后台层出现隐式拼接错误。
 */
function buildServiceUrl(service, path) {
  const baseUrl = SERVICE_BASE_URL[service]
  if (!baseUrl) {
    throw new Error(`不支持的服务类型: ${service}`)
  }

  const normalizedPath = String(path || '')
  if (!normalizedPath.startsWith('/')) {
    throw new Error(`请求路径必须以 / 开头: ${normalizedPath}`)
  }

  return `${baseUrl}${normalizedPath}`
}

/**
 * 为普通 HTTP 请求创建超时控制。
 *
 * 说明：
 * - 普通请求应尽快失败并把错误返回给页面侧。
 * - 流式请求不复用这套短超时，而是由调用方主动关闭连接。
 */
function createAbortSignal(timeoutMs = DEFAULT_HTTP_TIMEOUT_MS) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new Error('请求超时')), timeoutMs)

  return {
    signal: controller.signal,
    abort: () => controller.abort(),
    cleanup: () => clearTimeout(timer)
  }
}

/**
 * 将后台消息载荷转换成 fetch 选项。
 */
function createFetchOptions(payload, signal) {
  const options = {
    method: payload.method || 'GET',
    headers: payload.headers || {},
    signal
  }

  if (payload.body != null) {
    options.body = payload.body
  }

  return options
}

/**
 * 尽可能把响应体解析成调用方更容易消费的形态。
 *
 * 规则：
 * - JSON 返回对象
 * - 非 JSON 返回文本
 * - 204 返回 null
 */
async function parseResponseBody(response) {
  if (response.status === 204) return null

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return await response.json().catch(() => null)
  }

  return await response.text().catch(() => '')
}

/**
 * 处理普通 HTTP 请求。
 */
async function handleHttpRequest(payload) {
  const requestControl = createAbortSignal(payload.timeoutMs)

  try {
    const response = await fetch(
      buildServiceUrl(payload.service, payload.path),
      createFetchOptions(payload, requestControl.signal)
    )

    return {
      type: FASTFLOW_HTTP_RESPONSE,
      payload: {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        data: await parseResponseBody(response)
      }
    }
  } catch (error) {
    return {
      type: FASTFLOW_HTTP_RESPONSE,
      payload: {
        ok: false,
        status: 0,
        statusText: '',
        data: null,
        error: error instanceof Error ? error.message : '后台请求失败'
      }
    }
  } finally {
    requestControl.cleanup()
  }
}

/**
 * 处理 Nexus 的 SSE 流式请求，并把流事件转发给页面侧。
 *
 * 设计原因：
 * - 页面侧不能直接请求 HTTP 后端，否则会落入 Mixed Content / CORS / 宿主页隔离问题。
 * - 后台层负责读取 SSE，页面只消费已经解析好的业务事件。
 */
async function handleStream(port, payload, controller) {
  const decoder = new TextDecoder()
  let reader = null
  let streamClosed = false
  const postMessage = (message) => {
    try {
      port.postMessage(message)
    } catch {
      controller.abort()
    }
  }
  const closeStream = () => {
    if (streamClosed) return
    streamClosed = true
    postMessage({
      type: FASTFLOW_STREAM_CLOSE,
      payload: null
    })
    reader?.cancel().catch(() => {})
    controller.abort()
  }

  try {
    const response = await fetch(
      buildServiceUrl(payload.service, payload.path),
      createFetchOptions(payload, controller.signal)
    )

    if (!response.ok) {
      const errorBody = await parseResponseBody(response)
      postMessage({
        type: FASTFLOW_STREAM_ERROR,
        error:
          (errorBody && typeof errorBody === 'object' && (errorBody.message || errorBody.detail?.message)) ||
          (typeof errorBody === 'string' && errorBody) ||
          `Request failed with status ${response.status}`
      })
      return
    }

    if (!response.body) {
      postMessage({
        type: FASTFLOW_STREAM_ERROR,
        error: '流式响应体为空'
      })
      return
    }

    reader = response.body.getReader()
    const parser = createParser({
      onEvent(event) {
        const rawData = event?.data
        if (!rawData) return
        if (rawData === '[DONE]') {
          closeStream()
          return
        }

        try {
          postMessage({
            type: FASTFLOW_STREAM_EVENT,
            payload: JSON.parse(rawData)
          })
        } catch {
          // SSE 单条事件解析失败时跳过，不中断整条会话。
        }
      }
    })

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        if (!streamClosed) {
          parser.feed(decoder.decode())
          closeStream()
        }
        break
      }
      parser.feed(decoder.decode(value, { stream: true }))
      if (streamClosed) break
    }
  } catch (error) {
    if (streamClosed || controller.signal.aborted) return
    postMessage({
      type: FASTFLOW_STREAM_ERROR,
      error: error instanceof Error ? error.message : '流式请求失败'
    })
  } finally {
    controller.abort()
  }
}

export function initializeBackground() {
  if (backgroundInitialized) return
  backgroundInitialized = true

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.type !== FASTFLOW_HTTP_REQUEST) return false

    handleHttpRequest(message.payload)
      .then(sendResponse)
      .catch((error) => {
        sendResponse({
          type: FASTFLOW_HTTP_RESPONSE,
          payload: {
            ok: false,
            status: 0,
            statusText: '',
            data: null,
            error: error instanceof Error ? error.message : '后台请求失败'
          }
        })
      })

    return true
  })

  chrome.runtime.onConnect.addListener((port) => {
    if (port.name !== FASTFLOW_STREAM_PORT) return

    let closed = false
    let controller = null
    port.onDisconnect.addListener(() => {
      closed = true
      controller?.abort()
    })

    port.onMessage.addListener((message) => {
      if (closed || !message || message.type !== FASTFLOW_STREAM_OPEN) return
      controller = new AbortController()
      handleStream(port, message.payload, controller)
    })
  })
}

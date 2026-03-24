import { createParser } from 'eventsource-parser'

import { readRuntimeChannelOverrides, resolveRuntimeMode } from '@/extension/config/env'
import { resolveChannelConfig, resolveReleaseChannel } from '@/extension/config/channels'
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
let backgroundInitialized = false
let cachedServiceBaseUrl = null

function getServiceBaseUrlMap() {
  if (cachedServiceBaseUrl) return cachedServiceBaseUrl

  const releaseChannel = resolveReleaseChannel(resolveRuntimeMode())
  const config = resolveChannelConfig(
    releaseChannel,
    readRuntimeChannelOverrides(releaseChannel)
  )

  cachedServiceBaseUrl = {
    api: config.apiBaseUrl,
    nexus: config.nexusBaseUrl
  }
  return cachedServiceBaseUrl
}

/**
 * 将 service + path 组装成最终请求 URL。
 *
 * 这里强制要求 path 以 `/` 开头，避免后台层出现隐式拼接错误。
 */
function buildServiceUrl(service, path) {
  const baseUrl = getServiceBaseUrlMap()[service]
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
async function handleStream(port, payload, streamState) {
  const decoder = new TextDecoder()
  let reader = null
  let seenDoneSentinel = false
  let seenRunCompleted = false
  let seenErrorEvent = false

  const postMessage = (message) => {
    try {
      port.postMessage(message)
    } catch {
      streamState.closed = true
      streamState.controller?.abort()
    }
  }

  const postStreamError = (error) => {
    if (streamState.closed || streamState.cancelled) return
    seenErrorEvent = true
    postMessage({
      type: FASTFLOW_STREAM_ERROR,
      error
    })
    reader?.cancel().catch(() => {})
    streamState.controller?.abort()
  }

  const closeStream = () => {
    if (streamState.closed || streamState.cancelled) return
    streamState.closed = true
    postMessage({
      type: FASTFLOW_STREAM_CLOSE,
      payload: null
    })
    reader?.cancel().catch(() => {})
    streamState.controller?.abort()
  }

  try {
    const response = await fetch(
      buildServiceUrl(payload.service, payload.path),
      createFetchOptions(payload, streamState.controller.signal)
    )

    if (!response.ok) {
      const errorBody = await parseResponseBody(response)
      postStreamError(
        (errorBody && typeof errorBody === 'object' && (errorBody.message || errorBody.detail?.message)) ||
        (typeof errorBody === 'string' && errorBody) ||
        `Request failed with status ${response.status}`
      )
      return
    }

    if (!response.body) {
      postStreamError('流式响应体为空')
      return
    }

    reader = response.body.getReader()
    const parser = createParser({
      onEvent(event) {
        const rawData = event?.data
        if (!rawData) return
        if (rawData === '[DONE]') {
          seenDoneSentinel = true
          // `[DONE]` 只是传输结束哨兵；在看到业务完成态之前收到它，说明后端协议有问题。
          if (!seenRunCompleted && !seenErrorEvent) {
            postStreamError('SSE 会话在收到 run.completed 之前提前结束')
            return
          }
          closeStream()
          return
        }

        try {
          const payload = JSON.parse(rawData)
          // Background 不解释业务内容，只维护协议状态，并把事件立即转发给前端。
          if (payload?.type === 'run.completed') {
            seenRunCompleted = true
          }
          if (payload?.type === 'error') {
            seenErrorEvent = true
          }
          postMessage({
            type: FASTFLOW_STREAM_EVENT,
            payload
          })
        } catch {
          postStreamError('SSE 事件解析失败')
        }
      }
    })

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        if (!streamState.closed && !streamState.cancelled) {
          parser.feed(decoder.decode())
          // EOF 早于 `[DONE]` 也属于协议错误，不能静默当成成功关闭。
          if (!seenDoneSentinel) {
            postStreamError('SSE 会话在收到 [DONE] 之前提前断开')
          }
        }
        break
      }
      parser.feed(decoder.decode(value, { stream: true }))
      if (streamState.closed || streamState.cancelled) break
    }
  } catch (error) {
    if (streamState.closed || streamState.cancelled || streamState.controller.signal.aborted) return
    postStreamError(error instanceof Error ? error.message : '流式请求失败')
  } finally {
    streamState.controller.abort()
  }
}

function handleRuntimeMessage(message, _sender, sendResponse) {
  if (!message) return false

  if (message.type !== FASTFLOW_HTTP_REQUEST) return false

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
}

function handleRuntimeConnect(port) {
  if (port.name !== FASTFLOW_STREAM_PORT) return

  const streamState = {
    closed: false,
    cancelled: false,
    controller: null,
  }

  const notifyCancelled = () => {
    if (streamState.closed) return
    streamState.closed = true
    try {
      port.postMessage({
        type: FASTFLOW_STREAM_CANCELLED,
        payload: null,
      })
    } catch {
      // ignore
    }
  }

  port.onDisconnect.addListener(() => {
    streamState.closed = true
    streamState.cancelled = true
    streamState.controller?.abort()
  })

  port.onMessage.addListener((message) => {
    if (streamState.closed || !message) return

    if (message.type === FASTFLOW_STREAM_CANCEL) {
      if (streamState.cancelled) return
      streamState.cancelled = true
      streamState.controller?.abort()
      notifyCancelled()
      return
    }

    if (message.type !== FASTFLOW_STREAM_OPEN) return
    streamState.controller = new AbortController()
    handleStream(port, message.payload, streamState)
  })
}

function registerBackgroundListeners() {
  if (backgroundInitialized) return
  backgroundInitialized = true
  chrome.runtime.onMessage.addListener(handleRuntimeMessage)
  chrome.runtime.onConnect.addListener(handleRuntimeConnect)
}

// MV3 service worker 监听器必须在脚本初始求值阶段同步注册。
registerBackgroundListeners()

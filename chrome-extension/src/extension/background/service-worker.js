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
const STREAM_CANCEL_REQUEST_TIMEOUT_MS = 800
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

function extractErrorMessageFromBody(errorBody, fallbackMessage) {
  if (typeof errorBody === 'string' && errorBody.trim()) {
    return errorBody.trim()
  }

  if (!errorBody || typeof errorBody !== 'object') {
    return fallbackMessage
  }

  const directMessage = String(errorBody.message || '').trim()
  if (directMessage) return directMessage

  const detail = errorBody.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  if (detail && typeof detail === 'object') {
    const detailMessage = String(detail.message || '').trim()
    if (detailMessage) return detailMessage
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const firstDetail = detail[0]
    if (typeof firstDetail === 'string' && firstDetail.trim()) {
      return firstDetail.trim()
    }
    if (firstDetail && typeof firstDetail === 'object') {
      const firstDetailMessage = String(firstDetail.msg || firstDetail.message || '').trim()
      if (firstDetailMessage) return firstDetailMessage
    }
  }

  return fallbackMessage
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

function tryParseJsonBody(body) {
  if (body == null) return null
  if (typeof body === 'object') return body
  if (typeof body !== 'string') return null

  try {
    return JSON.parse(body)
  } catch {
    return null
  }
}

function extractStreamCancelPayload(payload) {
  if (!payload || payload.service !== 'nexus') return null

  const body = tryParseJsonBody(payload.body)
  const sessionId = String(body?.session_id || '').trim()
  const requestId = String(body?.request_id || '').trim()
  if (!sessionId || !requestId) return null

  return {
    headers: payload.headers || {},
    body: {
      session_id: sessionId,
      request_id: requestId,
    }
  }
}

async function requestStreamCancellation(streamState) {
  const cancelPayload = extractStreamCancelPayload(streamState.requestPayload)
  if (!cancelPayload) {
    return {
      status: 'not_cancellable',
      accepted: false
    }
  }

  const requestControl = createAbortSignal(STREAM_CANCEL_REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(
      buildServiceUrl('nexus', '/fastflow/nexus/v1/agent/chat/cancel'),
      createFetchOptions(
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...cancelPayload.headers,
          },
          body: JSON.stringify(cancelPayload.body),
        },
        requestControl.signal,
      ),
    )
    const responseBody = await parseResponseBody(response)
    if (!response.ok) {
      return {
        status: 'cancel_request_failed',
        accepted: false
      }
    }
    return {
      status: String(responseBody?.data?.status || '').trim() || 'cancel_request_failed',
      accepted: Boolean(responseBody?.data?.accepted),
    }
  } catch {
    return {
      status: 'cancel_request_failed',
      accepted: false
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
  let seenRunCompleted = false
  let seenErrorEvent = false

  const postMessage = (message) => {
    if (streamState.clientDetached) return
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
      postStreamError(extractErrorMessageFromBody(errorBody, `Request failed with status ${response.status}`))
      return
    }

    const contentType = String(response.headers.get('content-type') || '').toLowerCase()
    if (!contentType.includes('text/event-stream')) {
      const errorBody = await parseResponseBody(response)
      postStreamError(extractErrorMessageFromBody(errorBody, '服务端未返回 SSE 流'))
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
          // 新协议下，EOF 时必须已经见到业务终态。
          if (seenRunCompleted || seenErrorEvent) {
            closeStream()
          } else {
            postStreamError('SSE 会话在收到终态事件之前提前断开')
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
    cancelRequested: false,
    clientDetached: false,
    cancelRequestFinished: false,
    controller: null,
    requestPayload: null,
  }

  const notifyCancelled = (payload = null) => {
    if (streamState.closed || streamState.clientDetached) return
    streamState.closed = true
    try {
      port.postMessage({
        type: FASTFLOW_STREAM_CANCELLED,
        payload,
      })
    } catch {
      // ignore
    }
  }

  port.onDisconnect.addListener(() => {
    streamState.clientDetached = true
    if (streamState.cancelRequested && !streamState.cancelled) {
      return
    }
    streamState.closed = true
    streamState.cancelled = true
    streamState.controller?.abort()
  })

  port.onMessage.addListener((message) => {
    if (streamState.closed || !message) return

    if (message.type === FASTFLOW_STREAM_CANCEL) {
      if (streamState.cancelRequested || streamState.cancelled) return
      streamState.cancelRequested = true
      // 取消顺序必须是：
      // 1. 先把取消信号投递给后端活跃运行
      // 2. 再中断主 SSE 连接
      // 这样后端日志会先记录取消动作，再记录终态事件，时序更稳定。
      void requestStreamCancellation(streamState)
        .then((result) => {
          if (!result.accepted) {
            console.warn('[FastFlow] backend cancel request was not accepted', result)
          }
          return result
        })
        .catch(() => {
          return {
            status: 'cancel_request_failed',
            accepted: false
          }
        })
        .then((result) => {
          streamState.cancelRequestFinished = true
          streamState.cancelled = true
          streamState.controller?.abort()
          notifyCancelled(result)
        })
      return
    }

    if (message.type !== FASTFLOW_STREAM_OPEN) return
    streamState.controller = new AbortController()
    streamState.requestPayload = message.payload
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

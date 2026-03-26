import { backendClient } from '@/extension/runtime/backend-client.js'

function createProtocolError(message) {
  const error = new Error(message)
  error.code = 'FASTFLOW_STREAM_PROTOCOL_ERROR'
  return error
}

/**
 * 创建一个可取消的 agent 流式会话。
 *
 * 约定：
 * - 业务终态事件：`run.completed` / `error`
 * - transport close 只表示连接关闭
 * - 用户主动停止不会被当成错误
 */
export function startAgentStream(request, handlers = {}) {
  let finalGraph = null
  let seenRunCompleted = false
  let seenErrorEvent = false
  let settled = false
  let state = 'running'
  const session = {
    result: null,
    cancel() {},
    close() {},
    get state() {
      return state
    }
  }

  const result = new Promise((resolve, reject) => {
    function settleSuccess(payload = {}) {
      if (settled) return
      settled = true
      resolve({ finalGraph, ...payload })
    }

    function settleError(error) {
      if (settled) return
      settled = true
      reject(error)
    }

    const streamHandle = backendClient.stream({
      ...request,
      onEvent(event) {
        if (settled) return
        if (!event || !event.type) return

        if (event.type === 'graph') {
          finalGraph = event.data
        }
        if (event.type === 'run.completed') {
          seenRunCompleted = true
          state = 'completed'
        }
        if (event.type === 'error') {
          seenErrorEvent = true
          state = 'failed'
          handlers.onEvent?.(event)
          const error = new Error(event.message || event.error || 'Streaming error')
          handlers.onError?.(error)
          settleError(error)
          return
        }

        handlers.onEvent?.(event)
      },
      onComplete(payload) {
        if (settled) return

        if (payload?.cancelled) {
          state = 'cancelled'
          handlers.onCancelled?.(payload)
          settleSuccess(payload)
          return
        }

        if (!seenRunCompleted && !seenErrorEvent) {
          const error = createProtocolError('流式连接已关闭，但后端未发送终态事件(run.completed/error)')
          state = 'failed'
          handlers.onError?.(error)
          settleError(error)
          return
        }

        state = state === 'failed' ? 'failed' : 'completed'
        handlers.onComplete?.({ finalGraph })
        settleSuccess({ cancelled: false })
      },
      onError(error) {
        if (settled) return
        state = 'failed'
        handlers.onError?.(error)
        settleError(error)
      }
    })

    function cancel() {
      if (settled || state === 'cancelled' || state === 'cancelling') return
      state = 'cancelling'
      streamHandle.cancel()
    }

    function close() {
      if (settled) return
      streamHandle.close()
    }

    session.cancel = cancel
    session.close = close
  })

  session.result = result

  return session
}

import { authService } from '@/shared/services/auth.js'
import { startAgentStream } from '@/shared/services/agentStream.js'
import { Logger } from '@/shared/utils/logger.js'

function buildAgentRequestBody(params) {
  // 请求体协议保持稳定，便于后端 agent runtime 与前端输入层独立演进。
  return {
    mode: params.mode,
    user_prompt: params.prompt,
    execution_hints: params.executionHints ?? { selected_nodes: [], selected_skills: [] },
    session_id: params.sessionId,
    request_id: params.requestId,
    model_config_id: params.modelConfigId,
    workflow_graph: params.workflowGraph,
    workflow_meta: params.workflowMeta ?? null
  }
}

/**
 * 创建一个同步返回的 Nexus 会话。
 *
 * 设计原因：
 * - UI 需要先拿到 session，再接收任何流式回调。
 * - 如果把 token 获取和 stream 创建都放在 `await` 后面，错误回调可能早于 UI 注册活跃会话。
 * - 这里统一把“准备请求”和“运行请求”都收进同一个 session 生命周期里。
 */
function generateWorkflow(params, handlers = {}) {
  let innerSession = null
  let settled = false
  let state = 'running'
  let startCancelled = false
  let resolveResult = () => {}
  let rejectResult = () => {}

  const result = new Promise((resolve, reject) => {
    resolveResult = resolve
    rejectResult = reject
  })

  const session = {
    result,
    cancel() {
      if (settled || state === 'cancelled' || state === 'cancelling') return
      if (!innerSession) {
        startCancelled = true
        state = 'cancelled'
        settled = true
        const cancelPayload = {
          cancelled: true,
          cancelStatus: 'cancelled_before_start',
          cancelAccepted: false,
          finalGraph: null,
        }
        handlers.onCancelled?.(cancelPayload)
        resolveResult(cancelPayload)
        return
      }
      state = 'cancelling'
      innerSession.cancel()
    },
    close() {
      if (settled) return
      innerSession?.close()
    },
    get state() {
      return innerSession?.state || state
    }
  }

  ;(async () => {
    try {
      const token = await authService.getToken() || ''
      if (settled || startCancelled) return

      const requestHeaders = { 'Content-Type': 'application/json', 'Authorization': token }
      const body = buildAgentRequestBody(params)
      Logger.info('请求 Nexus Agent 详情', requestHeaders, body)

      innerSession = startAgentStream(
        {
          service: 'nexus',
          path: '/fastflow/nexus/v1/agent/chat/completions',
          method: 'POST',
          headers: requestHeaders,
          body,
        },
        {
          onEvent: handlers.onEvent,
          onCancelled: handlers.onCancelled,
          onComplete: ({ finalGraph } = {}) => {
            if (finalGraph) {
              handlers.onComplete?.(finalGraph)
              return
            }

            if (params.mode === 'builder') {
              handlers.onError?.(new Error('未收到 Nexus 返回的有效图数据'))
              return
            }

            handlers.onComplete?.(null)
          },
          onError(error) {
            Logger.error('Request Nexus Error:', error)
            handlers.onError?.(error)
          }
        }
      )

      innerSession.result
        .then((payload) => {
          if (settled) return
          settled = true
          state = innerSession?.state || state
          resolveResult(payload)
        })
        .catch((error) => {
          if (settled) return
          settled = true
          state = innerSession?.state || 'failed'
          rejectResult(error)
        })
    } catch (error) {
      if (settled) return
      settled = true
      state = 'failed'
      Logger.error('Request Nexus Error:', error)
      handlers.onError?.(error)
      rejectResult(error)
    }
  })()

  return session
}

export const Nexus = {
  generateWorkflow
}

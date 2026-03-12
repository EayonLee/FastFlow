import { authService } from '@/shared/services/auth.js'
import { backendClient } from '@/extension/runtime/backend-client.js'
import { Logger } from '@/shared/utils/logger.js'

/**
 * 生成工作流（调用 Nexus 的流式接口）
 * @param {Object} params - 请求参数
 * @param {string} params.mode - 智能体类型（chat / builder / debug）
 * @param {string} params.prompt - 用户输入的提示词
 * @param {string} params.sessionId - 会话 ID
 * @param {number} params.modelConfigId - 模型配置 ID（后端要求为数字）
 * @param {string|null} params.workflowGraph - 当前画布导出的原始 JSON 字符串（所有模式都传递）
 * @param {{workflow_name?: string, workflow_description?: string}|null} [params.workflowMeta] - 工作流元信息（可选）
 * @param {Function|null} onEvent - 统一事件回调（执行过程/回答增量）
 * @param {Function} onComplete - 成功回调（返回最终 graph）
 * @param {Function} onError - 错误回调（返回 Error）
 */
async function generateWorkflow(params, onEvent, onComplete, onError) {
  let finalGraph = null
  let streamHandle = null

  try {
    // 读取登录凭证（Nexus 接口需要 Authorization）
    const token = await authService.getToken() || ''

    // 组装请求体，字段名需与后端 AgentRequestContext 对齐
    const body = {
      mode: params.mode,
      user_prompt: params.prompt,
      session_id: params.sessionId,
      model_config_id: params.modelConfigId,
      workflow_graph: params.workflowGraph,
      workflow_meta: params.workflowMeta ?? null
    }

    // 发起请求（Nexus SSE 流式接口）
    const requestHeaders = { 'Content-Type': 'application/json', 'Authorization': token }
    Logger.info('请求 Nexus Agent 详情', requestHeaders, body)

    await new Promise((resolve, reject) => {
      streamHandle = backendClient.stream({
        service: 'nexus',
        path: '/fastflow/nexus/v1/agent/chat/completions',
        method: 'POST',
        headers: requestHeaders,
        body,
        onEvent(event) {
          onEvent?.(event)
          if (event.type === 'graph') {
            finalGraph = event.data
          }
          if (event.type === 'error') {
            reject(new Error(event.message || event.error || 'Streaming error'))
          }
        },
        onComplete() {
          if (finalGraph) {
            onComplete(finalGraph)
          } else if (params.mode === 'builder') {
            onError(new Error('未收到 Nexus 返回的有效图数据'))
          } else {
            onComplete(null)
          }
          resolve()
        },
        onError(error) {
          reject(error)
        }
      })
    })

  } catch (err) {
    // 网络错误或解析异常
    Logger.error('Request Nexus Error:', err)
    onError(err)
  } finally {
    streamHandle?.close()
  }
}

export const Nexus = {
  generateWorkflow
}

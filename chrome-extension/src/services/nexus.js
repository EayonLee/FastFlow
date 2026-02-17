import { authService } from '@/services/auth.js'
import { CONFIG } from '@/config/index.js'
import { Logger } from '@/utils/logger.js'
import { createParser } from 'eventsource-parser'

/**
 * 生成工作流（调用 Nexus 的流式接口）
 * @param {Object} params - 请求参数
 * @param {string} params.mode - 智能体类型（chat 或 builder）
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
  let streamErrorMessage = ''

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
    const response = await fetch(`${CONFIG.NEXUS_BASE_URL}/fastflow/nexus/v1/agent/chat/completions`, {
      method: 'POST',
      headers: requestHeaders,
      body: JSON.stringify(body)
    })
    Logger.info('请求 Nexus Agent 详情', requestHeaders, body, response)

    // 先读取后端错误（包含：非 2xx 或 2xx 但返回 JSON 错误体）
    const backendMessage = await readBackendError(response)
    if (backendMessage) {
      // 统一包装为 Error，交给调用方显示后端 message
      const error = new Error(backendMessage)
      Logger.error('Request Nexus Error:', error)
      onError(error)
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    const parser = createParser({
      onEvent(sseEvent) {
        const rawData = sseEvent?.data
        if (!rawData || rawData === '[DONE]') return
        try {
          const event = JSON.parse(rawData)
          if (onEvent) onEvent(event)
          if (event.type === 'error') {
            streamErrorMessage = event.message || event.error || 'Streaming error'
          }
          if (event.type === 'graph') {
            finalGraph = event.data
          }
        } catch (e) {
          // 单个 SSE 事件解析失败时跳过，避免阻塞整个流
        }
      }
    })

    // 逐块读取 SSE 数据并交给第三方解析器处理
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        parser.feed(decoder.decode())
        break
      }
      parser.feed(decoder.decode(value, { stream: true }))
    }
    
    // SSE 结束后，优先处理流式错误
    if (streamErrorMessage) {
      onError(new Error(streamErrorMessage))
      return
    }

    if (finalGraph) {
      // Builder 成功：返回图结构
      onComplete(finalGraph)
    } else {
      // Chat 不返回图；Builder 必须有图
      if (params.mode === 'builder') {
        onError(new Error('未收到 Nexus 返回的有效图数据'))
      } else {
        onComplete(null)
      }
    }

  } catch (err) {
    // 网络错误或解析异常
    Logger.error('Request Nexus Error:', err)
    onError(err)
  }
}

export const Nexus = {
  generateWorkflow
}

async function readBackendError(response) {
  // 非 2xx 直接解析错误信息
  if (!response.ok) {
    return await parseErrorResponse(response, `Request failed with status ${response.status}`)
  }
  // 2xx 但返回 JSON 错误体的场景（后端异常时可能出现）
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) return ''
  return await parseErrorResponse(response, '')
}

async function parseErrorResponse(response, fallback) {
  try {
    // 优先解析 JSON 格式的错误体
    const errorJson = await response.json()
    return (
      errorJson?.message ||
      errorJson?.detail?.message ||
      (Array.isArray(errorJson?.detail) ? errorJson.detail.map(d => d?.msg).filter(Boolean).join('; ') : '') ||
      errorJson?.detail ||
      fallback
    )
  } catch (e) {
    // JSON 解析失败则退回文本
    try {
      const text = await response.text()
      return text || fallback
    } catch (e2) {
      return fallback
    }
  }
}

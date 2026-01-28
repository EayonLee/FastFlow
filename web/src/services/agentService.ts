/**
 * 代理服务
 * 封装与 Nexus Agent 的交互逻辑
 */
import axios from 'axios'
import { useToast } from '@/composables/useToast'
import { useUserStore } from '@/stores/userStore'

// 创建 agent axios 实例
export const agentClient = axios.create({
  baseURL: '/fastflow/nexus/v1', // 通过 Vite 代理转发
  timeout: 60000, // Nexus 可能会处理较慢，设置更长的超时时间
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
agentClient.interceptors.request.use(
  (config) => {
    // 可以在这里添加认证 token 等
    const token = localStorage.getItem('Authorization')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
agentClient.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    const { showToast } = useToast()
    console.error('Nexus Error:', error)
    
    // 如果是取消请求，不显示错误
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }

    const msg = error.response?.data?.message || error.message || 'Network Error'
    showToast(`Nexus Error: ${msg}`, 'error')
    return Promise.reject(error)
  }
)

export interface StreamChatCallbacks {
  onChunk: (content: string) => void
  onGraphUpdate: (data: { type: 'layout' | 'graph', data: any }) => void
  onError: (message: string) => void
  onDone?: () => void
}

/**
 * 发起流式对话
 * @param payload 请求体
 * @param callbacks 回调函数集合
 * @param signal AbortSignal
 */
export async function streamChat(
  payload: any,
  callbacks: StreamChatCallbacks,
  signal?: AbortSignal
) {
  const token = localStorage.getItem('Authorization') || ''
  
  const response = await fetch('/fastflow/nexus/v1/agent/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    },
    body: JSON.stringify(payload),
    signal
  })

  const contentType = response.headers.get('content-type')
  if (!response.ok || contentType?.includes('application/json')) {
    let errorMsg = response.statusText
    try {
      const errorData = await response.json()
      // Check business code (if not 0 or 200, treat as error)
      const code = errorData.code
      if (code === 401) {
        // Handle 401 unauthorized
        const { logout } = useUserStore()
        logout()
        window.location.href = '/login'
        errorMsg = 'Session expired, please login again.'
      } else if (code !== undefined && code !== 0 && code !== 200) {
        errorMsg = errorData.message || `Error ${code}`
      } else if (errorData.message) {
        errorMsg = errorData.message
      } else if (errorData.detail) {
        // Handle FastAPI validation errors (422)
        if (Array.isArray(errorData.detail)) {
            errorMsg = errorData.detail.map((e: any) => `${e.loc?.join('.')} : ${e.msg}`).join('\n')
        } else {
            errorMsg = String(errorData.detail)
        }
      }
    } catch (e) {
      console.error('Failed to parse json error, response:' , response, e)
    }
    callbacks.onError(errorMsg)
    throw new Error(errorMsg)
  }

  if (!response.body) {
    throw new Error('No response body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6)
          if (dataStr === '[DONE]') continue
          
          try {
            const data = JSON.parse(dataStr)
            
            if (data.type === 'chunk') {
              callbacks.onChunk(data.content)
            } else if (data.type === 'layout' || data.type === 'graph') {
              callbacks.onGraphUpdate(data)
            } else if (data.type === 'error') {
              callbacks.onError(data.message)
            } else if (data.type === 'diff') {
              // diff 仅用于 UI 展示，当前无需特殊处理
              // 预留结构，避免未来新增类型时前端静默丢弃
            }
          } catch (e) {
            console.error('Failed to parse SSE message:', e)
          }
        }
      }
    }
  } finally {
    if (callbacks.onDone) callbacks.onDone()
  }
}

export default agentClient

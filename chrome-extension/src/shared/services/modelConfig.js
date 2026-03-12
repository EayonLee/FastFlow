import { authService } from '@/shared/services/auth.js'
import { backendClient } from '@/extension/runtime/backend-client.js'

// 获取模型配置列表（需要登录）
export async function getModelConfigs() {
  try {
    const token = await authService.getToken()
    const response = await backendClient.request({
      service: 'api',
      path: '/fastflow/api/v1/model_config/list',
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token || ''
      }
    })
    const result = response.data
    if (!response.ok || !result || result.code !== 200) {
      throw new Error(result?.message || 'get model config list failed')
    }
    return result.data || []
  } catch (error) {
    console.error('[FastFlow] Get model config list failed:', error)
    return []
  }
}

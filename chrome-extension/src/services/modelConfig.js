import { authService } from '@/services/auth.js'
import { CONFIG } from '@/config/index.js'

// 获取模型配置列表（需要登录）
export async function getModelConfigs() {
  try {
    const token = await authService.getToken()
    const response = await fetch(`${CONFIG.API_BASE_URL}/fastflow/api/v1/model_config/list`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token || ''
      }
    })
    const result = await response.json()
    if (!response.ok || !result || result.code !== 200) {
      throw new Error(result?.message || 'get model config list failed')
    }
    return result.data || []
  } catch (error) {
    console.error('[FastFlow] Get model config list failed:', error)
    return []
  }
}

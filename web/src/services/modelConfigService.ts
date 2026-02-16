import apiClient, { type ApiResponse } from './http'

export interface ModelConfigResponse {
  id: number
  modelName: string
  litellmModel: string
  provider?: string | null
  apiKey: string
  baseUrl?: string | null
  modelParamsJson?: string | null
  enabled: boolean
  userGroupId: string
  sortOrder: number
  createdAt: string
  updatedAt: string
}

// 获取模型配置列表的 Nexus
export const getModelConfigs = async (): Promise<ModelConfigResponse[]> => {
  try {
    const response = await apiClient.get<ApiResponse<ModelConfigResponse[]>>('/model_config/list')
    return response.data.data
  } catch (error) {
    console.error("get model config list failed", error)
    return []
  }
}

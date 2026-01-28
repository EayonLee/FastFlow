import apiClient, { type ApiResponse } from './http'

export interface ModelConfigResponse {
  id: number
  modelName: string
  modelId: string
  apiKey: string
  apiBase: string
  apiMode: string
  userGroupId: string
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

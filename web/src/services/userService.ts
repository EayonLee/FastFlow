import apiClient, { type ApiResponse } from './http'

// 获取当前用户信息
export const getUserInfo = async () => {
  const response = await apiClient.get<ApiResponse>('/user/info')
  return response.data.data
}

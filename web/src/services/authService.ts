import apiClient, { type ApiResponse } from './http'

// Auth Nexus
export const login = async (data: any) => {
  const response = await apiClient.post<ApiResponse>('/auth/login', data)
  return response.data
}

export const register = async (data: any) => {
  const response = await apiClient.post<ApiResponse>('/auth/register', data)
  return response.data
}

import axios from 'axios'
import { useToast } from '@/composables/useToast'

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL + '/fastflow/api/v1', // 使用环境变量定义的后端地址
  timeout: 30000, // 30秒超时
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 可以在这里添加认证 token 等
    const token = localStorage.getItem('Authorization')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    const uid = localStorage.getItem('uid')
    if (uid) {
      config.headers.uid = uid
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    const res = response.data
    // 判断业务状态码
    if (res && typeof res.code !== 'undefined' && res.code !== 200) {
      if (res.code === 401) {
        localStorage.removeItem('Authorization')
        localStorage.removeItem('uid')
        window.location.href = '/login'
      }

      const { showToast } = useToast()
      const message = res.message
      showToast(message, 'error');
      return Promise.reject(new Error(message))
    }
    return response
  },
  (error) => {
    const { showToast } = useToast()
    console.error('Nexus Error:', error)
    const msg = error.response?.data?.message || error.message || 'Network Error'
    
    // Handle 401 Unauthorized
    if (error.response?.status === 401) {
      localStorage.removeItem('Authorization')
      // Optional: redirect to login page
      window.location.href = '/login'
    }
    
    showToast(msg, 'error')
    return Promise.reject(error)
  }
)

export default apiClient

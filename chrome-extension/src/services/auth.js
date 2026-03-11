import { cache } from '@/utils/cache.js'
import { backendClient } from '@/services/backend-client.js'
import { PASSWORD_SECRET_KEY } from '@config'
import CryptoJS from 'crypto-js'

export const AUTH_EXPIRED_EVENT = 'auth-expired'
export const AUTHORIZATION_KEY = 'Authorization'
export const USER_INFO_KEY = 'userInfo'

// 统一清理本地认证信息
function clearAuthStorage() {
  cache.remove(AUTHORIZATION_KEY)
  cache.remove(USER_INFO_KEY)
}

// 通知登录过期（供 UI 做跳转）
function notifyAuthExpired() {
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT))
}

function buildApiError(result, fallbackMessage) {
  const error = new Error(result?.message || fallbackMessage)
  error.code = result?.code
  error.fieldErrors = result?.data?.fieldErrors || {}
  return error
}

// AES 加密函数
function encryptPassword(password) {
  const key = CryptoJS.enc.Utf8.parse(PASSWORD_SECRET_KEY)
  const srcs = CryptoJS.enc.Utf8.parse(password)
  const encrypted = CryptoJS.AES.encrypt(srcs, key, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7
  })
  return encrypted.toString()
}

export const authService = {
  async login(email, password) {
    try {
      // 对密码进行加密
      const encryptedPassword = encryptPassword(password)

      const response = await backendClient.request({
        service: 'api',
        path: '/fastflow/api/v1/auth/login',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: {
          email: email, 
          password: encryptedPassword 
        }
      })

      const result = response.data

      if (!response.ok || !result || result.code !== 200) {
        throw buildApiError(result, '登录失败，请检查账号密码')
      }
      
      // 登录成功，处理返回数据
      // 后端返回结构: { code: 200, data: { token: '...', userInfo: { ... } }, message: 'success' }
      const { token, userInfo } = result.data
      
      // 存储到 chrome.storage.local（由 cache.js 统一入口兜底）
      await cache.set(AUTHORIZATION_KEY, token)
      await cache.set(USER_INFO_KEY, userInfo)
      
      return userInfo
    } catch (error) {
      console.error('[FastFlow] Login error:', error)
      throw error
    }
  },

  async checkLogin() {
    const token = await cache.get(AUTHORIZATION_KEY)
    if (!token) {
      const err = new Error('Missing token')
      err.status = 401
      console.warn('[FastFlow] 登录状态已过期或未登录，已退出登录并清理本地缓存')
      clearAuthStorage()
      notifyAuthExpired()
      throw err
    }

    const response = await backendClient.request({
      service: 'api',
      path: '/fastflow/api/v1/auth/checkLogin',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token
      }
    })

    const result = response.data || null

    if (!response.ok || (result && result.code !== 200)) {
      const err = new Error((result && result.message) || '登录状态已过期')
      err.status = response.status
      // 登录失效：清理本地信息并通知 UI
      console.warn('[FastFlow] 登录状态已过期或未登录，已退出登录并清理本地缓存')
      clearAuthStorage()
      notifyAuthExpired()
      throw err
    }

    return result ? result.data : null
  },

  async register(data) {
    try {
      const encryptedPassword = encryptPassword(data.password)
      const response = await backendClient.request({
        service: 'api',
        path: '/fastflow/api/v1/auth/register',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: {
          username: data.username,
          email: data.email,
          password: encryptedPassword,
          inviteCode: data.inviteCode
        }
      })
      const result = response.data
      if (!response.ok || !result || result.code !== 200) {
        throw buildApiError(result, '注册失败')
      }
      return result.data
    } catch (error) {
      console.error('[FastFlow] Register error:', error)
      throw error
    }
  },

  logout() {
    // 清除本地存储的 Token 和用户信息
    clearAuthStorage()
  },

  async getCurrentUser() {
    return await cache.get(USER_INFO_KEY)
  },
  
  async getToken() {
    return await cache.get(AUTHORIZATION_KEY)
  },

  getAuthExpiredEventName() {
    return AUTH_EXPIRED_EVENT
  }
}

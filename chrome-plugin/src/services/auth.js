import { cache } from '@/utils/cache.js'
import { CONFIG } from '@/config/index.js'
import CryptoJS from 'crypto-js'

// 使用 config 中定义的 API_BASE_URL
const BASE_URL = CONFIG.API_BASE_URL
const PASSWORD_SECRET_KEY = CONFIG.PASSWORD_SECRET_KEY // 与后端保持一致
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

      const response = await fetch(`${BASE_URL}/fastflow/api/v1/auth/login`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json' 
        },
        body: JSON.stringify({ 
          email: email, 
          password: encryptedPassword 
        })
      })
      
      const result = await response.json()
      
      if (!response.ok || result.code !== 200) {
        throw new Error(result.message || '登录失败，请检查账号密码')
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

    const response = await fetch(`${BASE_URL}/fastflow/api/v1/auth/checkLogin`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token
      }
    })

    let result = null
    try {
      result = await response.json()
    } catch (e) {
      // ignore json parse errors
    }

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
    // 暂时保持 Mock，后续对接真实接口
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          success: true,
          message: '注册成功'
        })
      }, 1000)
    })
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

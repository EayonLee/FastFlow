/**
 * 本地存储缓存工具类
 * 支持设置过期时间
 */

import { StorageAdapter } from '@/utils/storageAdapter.js'

const adapter = new StorageAdapter('local')
const DEFAULT_TTL_MS = 5 * 60 * 1000

export const cache = {
  /**
   * 基础存取（无过期）
   */
  get(key) {
    return adapter.get(key)
  },
  set(key, value) {
    return adapter.set(key, value)
  },
  remove(key) {
    return adapter.remove(key)
  },
  onChanged(callback) {
    return adapter.onChanged(callback)
  },

  /**
   * 设置缓存
   * @param {string} key 键名
   * @param {any} value 值
   * @param {number} ttl 过期时间（毫秒），默认 5 分钟
   */
  async setWithTTL(key, value, ttl = DEFAULT_TTL_MS) {
    const item = {
      value,
      expiry: Date.now() + ttl
    }
    await adapter.set(key, item)
  },

  /**
   * 获取缓存
   * @param {string} key 键名
   * @returns {any|null} 值，如果过期或不存在则返回 null
   */
  async getWithTTL(key) {
    const item = await adapter.get(key)
    if (!item) return null

    try {
      // 检查是否过期
      if (Date.now() > item.expiry) {
        await adapter.remove(key)
        return null
      }
      
      return item.value
    } catch (e) {
      console.error('[FastFlow] Cache parse error:', e)
      return null
    }
  },

  /**
   * 移除缓存
   * @param {string} key 键名
   */
  async removeWithTTL(key) {
    await adapter.remove(key)
  }
}

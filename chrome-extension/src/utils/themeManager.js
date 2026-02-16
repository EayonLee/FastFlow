/**
 * Theme Manager
 * 核心职责：统一管理应用的主题状态，解耦 DOM 操作与状态逻辑。
 * 适用环境：Popup (普通 DOM) & Content Script (Shadow DOM)
 */

import { cache } from '@/utils/cache.js'

export class ThemeManager {
  constructor() {
    this.storageKey = 'theme'
    this.defaultTheme = 'dark'
    this.storage = cache
    this.targets = new Set()
    this.subscribers = new Set()
    this.currentTheme = this.defaultTheme

    /**
     * Content Script 与 Popup 属于不同上下文：
     * - 仅依赖 chrome.storage.onChanged 有概率出现异步延迟（用户体感为“切换慢/偶发没切过来”）
     * - 因此在 Popup 主动切主题时，额外向所有注入了 content script 的页面广播一次主题变更消息
     *   来做到“立即生效”（storage 只负责持久化，消息负责实时同步）。
     */
    this._initRuntimeThemeSync()
	    
    this.mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    this.mediaQuery.addEventListener('change', () => {
      if (this.currentTheme === 'system') {
        this.refresh()
      }
    })

    this.ready = this.init()
  }

  /**
   * 初始化运行时主题同步：
   * - content script：监听来自 popup 的主题消息，立即更新 UI
   * - popup：也会注册监听，但不会收到 tabs.sendMessage 的广播（可忽略）
   */
  _initRuntimeThemeSync() {
    try {
      if (!chrome?.runtime?.onMessage?.addListener) return
      chrome.runtime.onMessage.addListener((msg) => {
        if (!msg || msg.type !== 'FASTFLOW_THEME_UPDATE') return
        const theme = msg.theme
        if (!theme) return
        this._setCurrentTheme(theme)
      })
    } catch (_) {
      // ignore
    }
  }

  /**
   * 只更新内存态并刷新 UI（不写 storage，不再触发二次广播）。
   * 说明：用于处理 storage.onChanged / runtime message 等“外部事件”。
   */
  _setCurrentTheme(theme) {
    if (!theme || this.currentTheme === theme) return
    this.currentTheme = theme
    this.refresh()
  }

  /**
   * 向所有 tab 的 content script 广播主题更新（仅 popup 环境可用）。
   * 说明：不依赖 background/service worker，直接 tabs.sendMessage 即可。
   */
  async _broadcastThemeToTabs(theme) {
    try {
      if (!chrome?.tabs?.query || !chrome?.tabs?.sendMessage) return
      const tabs = await new Promise((resolve) => chrome.tabs.query({}, resolve))
      for (const tab of tabs || []) {
        if (!tab?.id) continue
        try {
          chrome.tabs.sendMessage(tab.id, { type: 'FASTFLOW_THEME_UPDATE', theme }, () => {
            // 部分页面（如 chrome://）会失败，忽略即可
            void chrome.runtime?.lastError
          })
        } catch (_) {
          // ignore
        }
      }
    } catch (_) {
      // ignore
    }
  }

  register(element) {
    if (element) {
      this.targets.add(element)
      this.applyTo(element)
    }
  }

  subscribe(callback) {
    if (!callback) return () => {}
    this.subscribers.add(callback)
    callback(this.currentTheme)
    return () => this.subscribers.delete(callback)
  }

  async init() {
    const stored = await this.storage.get(this.storageKey)
    if (stored === undefined) {
      await this.storage.set(this.storageKey, this.defaultTheme)
      this.currentTheme = this.defaultTheme
    } else {
      this.currentTheme = stored
    }

    this.unsubscribeStorage = this.storage.onChanged((changes) => {
      const change = changes?.[this.storageKey]
      if (!change) return
      const newValue = change.newValue
      if (newValue === undefined) return
      this._setCurrentTheme(newValue)
    })

    this.refresh()
  }

  resolveTheme() {
    if (this.currentTheme === 'system') {
      return this.mediaQuery.matches ? 'dark' : 'light'
    }
    return this.currentTheme
  }

  applyTo(element) {
    const resolved = this.resolveTheme()
    element.setAttribute('data-theme', resolved)
  }

  refresh() {
    this.targets.forEach((el) => this.applyTo(el))
    this.subscribers.forEach((cb) => cb(this.currentTheme))
  }

  async setTheme(theme) {
    // 先在当前上下文立即生效（减少体感延迟）
    this._setCurrentTheme(theme)
    // 再广播给所有 tab，确保 content script 立即同步（减少“偶发没切过来”的情况）
    await this._broadcastThemeToTabs(theme)
    // 最后持久化，供后续页面/重启恢复
    await this.storage.set(this.storageKey, theme)
  }

  getTheme() {
    return this.currentTheme
  }
}

// 单例模式导出
export const themeManager = new ThemeManager()

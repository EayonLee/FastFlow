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
    
    this.mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    this.mediaQuery.addEventListener('change', () => {
      if (this.currentTheme === 'system') {
        this.refresh()
      }
    })

    this.ready = this.init()
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
      if (this.currentTheme === newValue) return
      this.currentTheme = newValue
      this.refresh()
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
    this.currentTheme = theme
    this.refresh()
    await this.storage.set(this.storageKey, theme)
  }

  getTheme() {
    return this.currentTheme
  }
}

// 单例模式导出
export const themeManager = new ThemeManager()

import { Logger } from '@/shared/utils/logger.js'
import { themeManager } from '@/shared/utils/themeManager.js'
import { createApp } from 'vue'
import App from './App.vue'

// 引入样式文件
import variablesCss from '@/shared/styles/variables.css?inline'
import baseCss from '@/shared/styles/base.css?inline'
import chatCss from '@/shared/styles/components/chat.css?inline'
import flowSelectCss from '@/shared/styles/components/flow-select.css?inline'
import headerCss from '@/shared/styles/components/header.css?inline'
import agentRuntimeCss from '@/shared/styles/components/agent-runtime.css?inline'

/**
 * MountManager
 * 职责：管理 Content Script 中 UI 的挂载生命周期，包括 Shadow DOM 的创建与清理
 */
export class MountManager {
  constructor() {
    this.hostId = 'fastflow-copilot-host'
    this.appInstance = null
    this.hostElement = null
  }

  /**
   * 当前 UI 是否已经挂载。
   *
   * 这里同时检查 `appInstance` 与宿主节点，避免出现“实例引用还在，但 DOM 已被页面重建移除”的假阳性。
   */
  isMounted() {
    return Boolean(this.appInstance && document.getElementById(this.hostId))
  }

  /**
   * 初始化并挂载 Vue 应用
   */
  mount() {
    if (this.isMounted()) return

    Logger.info('Initializing Vue UI...')

    // 1. 清理可能存在的旧实例
    this.cleanup()

    // 2. 创建宿主容器
    this.hostElement = this.createHostElement()
    document.body.appendChild(this.hostElement)

    // 3. 注册到 ThemeManager，实现主题同步
    themeManager.register(this.hostElement)

    // 4. 创建 Shadow DOM 环境
    const shadow = this.hostElement.attachShadow({ mode: 'open' })
    this.injectStyles(shadow)

    // 5. 挂载 Vue 应用
    const appRoot = document.createElement('div')
    appRoot.id = 'app'
    shadow.appendChild(appRoot)

    this.appInstance = createApp(App)
    this.appInstance.mount(appRoot)

    Logger.info('Vue App Mounted')
  }

  /**
   * 创建宿主 DOM 元素
   */
  createHostElement() {
    const host = document.createElement('div')
    host.id = this.hostId
    
    // 基础样式配置，确保不干扰页面布局
    Object.assign(host.style, {
      position: 'fixed',
      zIndex: '2147483647',
      top: '0',
      left: '0',
      width: '0',
      height: '0',
      overflow: 'visible'
    })

    return host
  }

  /**
   * 注入样式到 Shadow DOM
   */
  injectStyles(shadowRoot) {
    const styleTag = document.createElement('style')
    styleTag.textContent = [
      variablesCss, 
      baseCss, 
      chatCss, 
      flowSelectCss, 
      headerCss,
      agentRuntimeCss
    ].join('\n')
    shadowRoot.appendChild(styleTag)
  }

  /**
   * 清理实例
   */
  cleanup() {
    if (this.appInstance) {
      this.appInstance.unmount()
      this.appInstance = null
    }

    const existing = document.getElementById(this.hostId)
    if (existing) {
      Logger.info('Cleaning up old instance...')
      existing.remove()
    }

    this.hostElement = null
  }
}

// 单例导出
export const mountManager = new MountManager()

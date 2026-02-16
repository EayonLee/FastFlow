/**
 * FastFlow Chrome 插件主入口文件
 * 作用：初始化 Vue 应用，创建 Shadow DOM 容器，并将其挂载到宿主页面上。
 */

import { Bridge } from '@/services/bridge.js'
import { Detector } from '@/utils/detector.js'
import { Logger } from '@/utils/logger.js'
import { mountManager } from './mount.js'

let appInitialized = false

/**
 * 主函数
 * 负责环境检测和启动流程
 */
function main() {
  if (appInitialized) return

  // 检测是否在目标环境中（例如编排画布页面）
  if (Detector.check()) {
    const env = Detector.getEnvInfo()
    Logger.info(`在 [${env}] 中检测到编排画布，正在初始化...`)

    // 1. 注入通信桥接脚本
    Bridge.injectScript()

    // 2. 初始化 UI (使用新的 MountManager)
    mountManager.mount()

    appInitialized = true
  }
}

function scheduleInit() {
  setTimeout(main, 100)
}

// 确保在页面加载完成后执行 main
if (document.readyState === 'complete' || document.readyState === 'interactive') {
  scheduleInit()
}

// 使用 MutationObserver 监听 DOM 变化，应对单页应用 (SPA) 的动态渲染
const observer = new MutationObserver(() => {
  if (!appInitialized) {
    main()
  }
})

if (document.body) {
  observer.observe(document.body, { childList: true, subtree: true })
  scheduleInit()
} else {
  window.addEventListener('DOMContentLoaded', () => {
    observer.observe(document.body, { childList: true, subtree: true })
    scheduleInit()
  })
}

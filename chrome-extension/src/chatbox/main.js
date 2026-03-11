/**
 * FastFlow Chrome 插件主入口文件。
 *
 * 该入口不再只负责“首次初始化”，而是持续同步插件 UI 与宿主页面的状态：
 * - 当前页面存在工作流画布：挂载右下角入口与聊天面板
 * - 当前页面离开工作流画布：立即卸载插件 UI
 *
 * 这样在单页应用（SPA）里从画布页跳到其他页面时，不会出现右下角小球残留。
 */

import { Detector } from '@/utils/detector.js'
import { Logger } from '@/utils/logger.js'
import { mountManager } from './mount.js'

let syncScheduled = false

/**
 * 根据当前页面是否仍然存在工作流画布，同步插件 UI 的挂载状态。
 *
 * 这是内容脚本的核心生命周期入口：
 * - 只要检测到画布，就确保 UI 已挂载
 * - 一旦检测不到画布，就立即卸载 UI
 */
function syncMountState() {
  syncScheduled = false
  const hasWorkflowCanvas = Detector.check()

  if (hasWorkflowCanvas) {
    const env = Detector.getEnvInfo()
    if (mountManager.isMounted()) return

    Logger.info(`在 [${env}] 中检测到编排画布，正在初始化...`)

    // 通信桥接脚本改为按需注入：
    // - 启动阶段只挂载 UI，不再做预热注入
    // - 真正导出工作流、读取元信息、无感渲染时再由 Bridge 触发注入
    // 这样可以避免页面刚进入时因为宿主脚本尚未稳定而产生“预热超时”的无效报错
    mountManager.mount()
    return
  }

  if (!mountManager.isMounted()) return

  Logger.info('未检测到编排画布，正在卸载插件 UI...')
  mountManager.cleanup()
}

/**
 * 将频繁的 DOM / 路由变化合并为一次状态同步，避免在 SPA 页面中重复 mount/unmount。
 */
function scheduleSync() {
  if (syncScheduled) return
  syncScheduled = true
  window.setTimeout(syncMountState, 50)
}

function bindRouteChangeListeners() {
  const schedule = () => scheduleSync()
  window.addEventListener('popstate', schedule)
  window.addEventListener('hashchange', schedule)

  const { pushState, replaceState } = window.history
  window.history.pushState = function (...args) {
    const result = pushState.apply(this, args)
    scheduleSync()
    return result
  }
  window.history.replaceState = function (...args) {
    const result = replaceState.apply(this, args)
    scheduleSync()
    return result
  }
}

const observer = new MutationObserver(() => {
  scheduleSync()
})

if (document.body) {
  observer.observe(document.body, { childList: true, subtree: true })
  bindRouteChangeListeners()
  scheduleSync()
} else {
  window.addEventListener('DOMContentLoaded', () => {
    observer.observe(document.body, { childList: true, subtree: true })
    bindRouteChangeListeners()
    scheduleSync()
  })
}

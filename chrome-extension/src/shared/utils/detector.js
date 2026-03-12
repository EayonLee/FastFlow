import { runtimeConfig } from '@/extension/config/runtime'

/**
 * 判断节点是否“可见且可交互”。
 *
 * 设计原因：
 * - SPA 场景下，离开画布后旧节点可能仍留在 DOM（如 keep-alive / hidden 容器）
 * - 仅用 querySelector 命中会导致误判“仍在画布页”，从而不触发插件卸载
 * - 结果就是 session_id 被错误复用
 *
 * 因此这里要求：
 * 1) 节点仍连接在文档中
 * 2) display / visibility 不隐藏
 * 3) 有实际渲染尺寸（width/height > 0）
 */
function isVisibleCanvasElement(element) {
  if (!element || !element.isConnected) return false
  const style = window.getComputedStyle(element)
  if (style.display === 'none' || style.visibility === 'hidden') return false
  const rect = element.getBoundingClientRect()
  return rect.width > 0 && rect.height > 0
}

function check() {
  // 必须命中“可见画布节点”才算在画布页。
  // 这样退出画布时会触发 mountManager.cleanup()，重新进入时会重新 mount（新会话）。
  return runtimeConfig.elementSelectors.some((selector) => {
    const matchedElements = document.querySelectorAll(selector)
    for (const element of matchedElements) {
      if (isVisibleCanvasElement(element)) return true
    }
    return false
  })
}

function getEnvInfo() {
  return window.self === window.top ? 'Main Window' : 'Iframe'
}

export const Detector = {
  check,
  getEnvInfo
}

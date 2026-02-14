/**
 * Mermaid 主题同步（Content Script 专用）
 * - 主题切换时，已渲染的 Mermaid SVG 不会自动换色（Mermaid 不支持 themeVariables 使用 var()）
 * - 因此在主题变化时，主动触发一次“重渲染”（并复用源码缓存），保证图与主题一致
 * - 同时使用微任务节流，避免连点切换触发多次重渲染导致卡顿
 */

import { onMounted, onBeforeUnmount } from 'vue'
import { themeManager } from '@/utils/themeManager.js'
import { rerenderMermaidInElement } from '@/utils/mermaid.js'

export function useMermaidThemeSync(messagesContainerRef) {
  let unsubscribe = null
  let scheduled = false

  function scheduleRerender() {
    if (scheduled) return
    scheduled = true
    queueMicrotask(async () => {
      scheduled = false
      const rootEl = messagesContainerRef?.value
      if (!rootEl) return
      await rerenderMermaidInElement(rootEl)
    })
  }

  onMounted(async () => {
    await themeManager.ready
    unsubscribe = themeManager.subscribe(() => {
      // 当前上下文的主题状态已经在 ThemeManager 内更新，此处只触发重渲染即可
      scheduleRerender()
    })
  })

  onBeforeUnmount(() => {
    if (unsubscribe) unsubscribe()
    unsubscribe = null
  })
}


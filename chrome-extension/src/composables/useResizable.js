import { cache } from '@/utils/cache.js'

// 默认尺寸与边距约束
const DEFAULT_MIN_WIDTH = 360
const DEFAULT_MIN_HEIGHT = 520
const DEFAULT_EDGE_PADDING = 60

export function useResizable(containerRef, options = {}) {
  // 最小尺寸与边距约束（避免拖出屏幕）
  const minWidth = options.minWidth ?? DEFAULT_MIN_WIDTH
  const minHeight = options.minHeight ?? DEFAULT_MIN_HEIGHT
  const edgePadding = options.edgePadding ?? DEFAULT_EDGE_PADDING
  // 拖拽状态变化回调（用于 UI 表现）
  const onResizeStateChange = options.onResizeStateChange
  // 缓存 key（用于记住尺寸）
  const storageKey = options.storageKey

  // 拖拽中的临时状态
  let resizeState = null
  // 使用 RAF 节流，提升拖拽流畅度
  let rafId = null
  // 最近一次 pointer 事件（用于 RAF 更新）
  let pendingEvent = null

  // 计算最大宽度：不超过视窗，保留边距
  function getMaxWidth() {
    return Math.max(minWidth, window.innerWidth - edgePadding)
  }

  // 计算最大高度：不超过视窗，保留边距
  function getMaxHeight() {
    return Math.max(minHeight, window.innerHeight - edgePadding)
  }

  // 通知外部当前是否正在拖拽
  function setResizing(active) {
    if (!onResizeStateChange) return
    onResizeStateChange(active)
  }

  // 根据指针增量更新尺寸
  function updateSize() {
    if (!resizeState || !pendingEvent) return
    const { startX, startY, startWidth, startHeight, el, dir } = resizeState
    const { clientX, clientY } = pendingEvent
    const deltaX = clientX - startX
    const deltaY = clientY - startY
    // 方向标识：含 w/n 表示向左/向上拖动时尺寸增大
    const widthSign = dir.includes('w') ? -1 : 1
    const heightSign = dir.includes('n') ? -1 : 1
    const nextWidth = startWidth + (deltaX * widthSign)
    const nextHeight = startHeight + (deltaY * heightSign)
    const width = Math.min(getMaxWidth(), Math.max(minWidth, nextWidth))
    const height = Math.min(getMaxHeight(), Math.max(minHeight, nextHeight))
    el.style.width = `${width}px`
    el.style.height = `${height}px`
  }

  // 将尺寸应用到容器（带最小/最大边界）
  function applySize(el, size) {
    if (!el || !size) return
    const width = Math.min(getMaxWidth(), Math.max(minWidth, size.width || minWidth))
    const height = Math.min(getMaxHeight(), Math.max(minHeight, size.height || minHeight))
    el.style.width = `${width}px`
    el.style.height = `${height}px`
  }

  // 从缓存中恢复尺寸
  async function restoreSize() {
    if (!storageKey) return
    const el = containerRef.value
    if (!el) return
    const saved = await cache.get(storageKey)
    if (!saved) return
    applySize(el, saved)
  }

  // 将当前尺寸写入缓存
  async function persistSize() {
    if (!storageKey || !resizeState) return
    const { el } = resizeState
    if (!el) return
    await cache.set(storageKey, {
      width: el.offsetWidth,
      height: el.offsetHeight
    })
  }

  // 使用 RAF 节流拖拽更新，避免卡顿
  function scheduleResize(e) {
    pendingEvent = e
    if (rafId) return
    rafId = window.requestAnimationFrame(() => {
      rafId = null
      updateSize()
    })
  }

  // 停止拖拽并保存尺寸
  async function stopResize(e) {
    if (!resizeState) return
    const { handleEl } = resizeState
    if (handleEl?.releasePointerCapture && e?.pointerId != null) {
      try {
        handleEl.releasePointerCapture(e.pointerId)
      } catch (err) {
        // ignore
      }
    }
    window.removeEventListener('pointermove', scheduleResize)
    window.removeEventListener('pointerup', stopResize)
    await persistSize()
    resizeState = null
    pendingEvent = null
    if (rafId) {
      window.cancelAnimationFrame(rafId)
      rafId = null
    }
    setResizing(false)
  }

  // 开始拖拽：记录起始尺寸与方向
  function startResize(dir, e) {
    const el = containerRef.value
    if (!el) return
    e.preventDefault()
    e.stopPropagation()
    resizeState = {
      el,
      dir,
      handleEl: e.currentTarget,
      startX: e.clientX,
      startY: e.clientY,
      startWidth: el.offsetWidth,
      startHeight: el.offsetHeight
    }
    // 使用 pointer capture，保证拖拽过程不中断
    if (resizeState.handleEl?.setPointerCapture && e.pointerId != null) {
      resizeState.handleEl.setPointerCapture(e.pointerId)
    }
    window.addEventListener('pointermove', scheduleResize)
    window.addEventListener('pointerup', stopResize)
    setResizing(true)
  }

  // 清理拖拽状态与监听
  function cleanup() {
    stopResize()
  }

  return {
    startResize,
    restoreSize,
    cleanup
  }
}

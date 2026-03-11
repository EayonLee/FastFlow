import { cache } from '@/utils/cache.js'

export const DEFAULT_MIN_WIDTH = 360
export const DEFAULT_MIN_HEIGHT = 520
const DEFAULT_EDGE_PADDING = 60

function clampDimension(value, preferredMin, max) {
  const safeMax = Math.max(0, max)
  const safeMin = Math.min(preferredMin, safeMax)
  return Math.min(safeMax, Math.max(safeMin, value))
}

function resolveAnchorSide(anchorSide, dir) {
  if (anchorSide === 'left' || anchorSide === 'right') {
    return anchorSide
  }
  return dir.includes('w') ? 'right' : 'left'
}

function computeHorizontalRect(startRect, deltaX, anchorSide, minWidth, edgePadding) {
  if (anchorSide === 'left') {
    const left = startRect.left
    const maxWidth = window.innerWidth - edgePadding - left
    const width = clampDimension(startRect.width + deltaX, minWidth, maxWidth)
    return {
      left,
      width,
      right: left + width
    }
  }

  const right = startRect.right
  const maxWidth = right - edgePadding
  const width = clampDimension(startRect.width - deltaX, minWidth, maxWidth)
  return {
    left: right - width,
    width,
    right
  }
}

function computeVerticalRect(startRect, deltaY, dir, minHeight, edgePadding) {
  if (dir.includes('n')) {
    const bottom = startRect.bottom
    const maxHeight = bottom - edgePadding
    const height = clampDimension(startRect.height - deltaY, minHeight, maxHeight)
    return {
      top: bottom - height,
      height,
      bottom
    }
  }

  const top = startRect.top
  const maxHeight = window.innerHeight - edgePadding - top
  const height = clampDimension(startRect.height + deltaY, minHeight, maxHeight)
  return {
    top,
    height,
    bottom: top + height
  }
}

function buildNextRect(resizeState, pointerEvent, minWidth, minHeight, edgePadding) {
  const { startX, startY, startRect, dir, anchorSide } = resizeState
  const deltaX = pointerEvent.clientX - startX
  const deltaY = pointerEvent.clientY - startY
  const horizontal = computeHorizontalRect(startRect, deltaX, anchorSide, minWidth, edgePadding)
  const vertical = computeVerticalRect(startRect, deltaY, dir, minHeight, edgePadding)

  return {
    left: horizontal.left,
    top: vertical.top,
    width: horizontal.width,
    height: vertical.height,
    right: horizontal.right,
    bottom: vertical.bottom
  }
}

export function useResizable(options = {}) {
  const minWidth = options.minWidth ?? DEFAULT_MIN_WIDTH
  const minHeight = options.minHeight ?? DEFAULT_MIN_HEIGHT
  const edgePadding = options.edgePadding ?? DEFAULT_EDGE_PADDING
  const onResize = options.onResize
  const onResizeEnd = options.onResizeEnd
  const onResizeStateChange = options.onResizeStateChange
  const storageKey = options.storageKey

  let resizeState = null
  let pendingEvent = null
  let rafId = null

  function setResizing(active) {
    if (typeof onResizeStateChange === 'function') {
      onResizeStateChange(active)
    }
  }

  function emitResize() {
    if (!resizeState || !pendingEvent) return
    const nextRect = buildNextRect(resizeState, pendingEvent, minWidth, minHeight, edgePadding)
    resizeState.lastRect = nextRect
    if (typeof onResize === 'function') {
      onResize(nextRect, {
        dir: resizeState.dir,
        anchorSide: resizeState.anchorSide
      })
    }
  }

  function scheduleResize(event) {
    pendingEvent = event
    if (rafId) return
    rafId = window.requestAnimationFrame(() => {
      rafId = null
      emitResize()
    })
  }

  async function persistSize(rect) {
    if (!storageKey || !rect) return
    await cache.set(storageKey, {
      width: rect.width,
      height: rect.height
    })
  }

  async function stopResize(event) {
    if (!resizeState) return
    const { handleEl, dir, anchorSide } = resizeState
    if (handleEl?.releasePointerCapture && event?.pointerId != null) {
      try {
        handleEl.releasePointerCapture(event.pointerId)
      } catch (error) {
        // ignore release failures
      }
    }

    window.removeEventListener('pointermove', scheduleResize)
    window.removeEventListener('pointerup', stopResize)

    if (rafId) {
      window.cancelAnimationFrame(rafId)
      rafId = null
    }

    const finalRect = resizeState.lastRect || resizeState.startRect
    await persistSize(finalRect)

    if (typeof onResizeEnd === 'function') {
      onResizeEnd(finalRect, { dir, anchorSide })
    }

    resizeState = null
    pendingEvent = null
    setResizing(false)
  }

  function startResize(dir, event, context = {}) {
    const rect = context.rect
    if (!rect) return

    event.preventDefault()
    event.stopPropagation()

    const handleEl = event.currentTarget
    const anchorSide = resolveAnchorSide(context.anchorSide, dir)
    const startRect = {
      left: rect.left,
      top: rect.top,
      width: rect.width,
      height: rect.height,
      right: rect.right ?? rect.left + rect.width,
      bottom: rect.bottom ?? rect.top + rect.height
    }

    resizeState = {
      dir,
      anchorSide,
      handleEl,
      startRect,
      lastRect: startRect,
      startX: event.clientX,
      startY: event.clientY
    }

    if (handleEl?.setPointerCapture && event.pointerId != null) {
      handleEl.setPointerCapture(event.pointerId)
    }

    if (typeof onResize === 'function') {
      onResize(startRect, { dir, anchorSide })
    }

    window.addEventListener('pointermove', scheduleResize)
    window.addEventListener('pointerup', stopResize)
    setResizing(true)
  }

  async function restoreSize() {
    if (!storageKey) return null
    const saved = await cache.get(storageKey)
    if (!saved) return null
    return {
      width: Math.max(Number(saved.width) || minWidth, minWidth),
      height: Math.max(Number(saved.height) || minHeight, minHeight)
    }
  }

  function cleanup() {
    return stopResize()
  }

  return {
    cleanup,
    restoreSize,
    startResize
  }
}

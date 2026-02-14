<script setup>
/**
 * Mermaid 放大预览组件
 * - 负责 SVG 的拖拽/缩放（svg-pan-zoom）
 * - 负责工具条交互：放大/缩小/重置/复制语句/下载图片
 *
 * 注意：
 * - 这里使用 v-html 注入 SVG 字符串，所以所有 DOM 查询都必须基于组件自身根节点来做。
 * - 预览层必须随聊天窗尺寸变化而自适配，因此需要 ResizeObserver 通知 svg-pan-zoom 重新计算。
 */
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { Check, ZoomIn, ZoomOut, RotateCcw, X, FileCode, ImageDown } from 'lucide-vue-next'
import { copyTextToClipboard } from '@/utils/clipboard.js'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  svgHtml: {
    type: String,
    default: ''
  },
  source: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close'])

const rootRef = ref(null)
let svgPanZoomInstance = null
let onViewerKeydown = null
let viewerResizeObserver = null
let onViewerWheel = null

const viewerCopiedSource = ref(false)
const viewerDownloadedImage = ref(false)
let copiedSourceTimer = null
let downloadedImageTimer = null

async function ensureSvgPanZoom() {
  // 按需加载，避免不使用时增加首包体积
  const mod = await import('svg-pan-zoom')
  // svg-pan-zoom 是 CJS 包：不同构建路径下导出形态可能不同，这里显式选择“函数导出”。
  const candidates = [mod?.default, mod?.s?.default, mod?.s, mod]
  const fn = candidates.find((c) => typeof c === 'function')
  if (!fn) {
    throw new Error('svg-pan-zoom 模块未导出可调用函数（构建导出形态不符合预期）')
  }
  return fn
}

function _clearTimersAndFlags() {
  viewerCopiedSource.value = false
  viewerDownloadedImage.value = false
  if (copiedSourceTimer) {
    clearTimeout(copiedSourceTimer)
    copiedSourceTimer = null
  }
  if (downloadedImageTimer) {
    clearTimeout(downloadedImageTimer)
    downloadedImageTimer = null
  }
}

function _destroyPanZoom() {
  if (svgPanZoomInstance) {
    try {
      svgPanZoomInstance.destroy()
    } catch (_) {
      // ignore
    }
    svgPanZoomInstance = null
  }
}

function _teardownListeners() {
  const canvasEl = rootRef.value?.querySelector?.('.mermaid-viewer-canvas')
  if (canvasEl && onViewerWheel) {
    canvasEl.removeEventListener('wheel', onViewerWheel, { capture: true })
    onViewerWheel = null
  }

  if (viewerResizeObserver) {
    try {
      viewerResizeObserver.disconnect()
    } catch (_) {
      // ignore
    }
    viewerResizeObserver = null
  }

  if (onViewerKeydown) {
    window.removeEventListener('keydown', onViewerKeydown, true)
    onViewerKeydown = null
  }
}

function cleanupViewer() {
  _clearTimersAndFlags()
  _destroyPanZoom()
  _teardownListeners()
}

function close() {
  emit('close')
}

async function initPanZoomIfNeeded() {
  await nextTick()
  const svgEl = rootRef.value?.querySelector?.('.mermaid-viewer-canvas svg')
  if (!svgEl) return

  // 强制 SVG 填满画布，避免 Mermaid 内联 width/height/style 导致只显示一小块。
  try {
    svgEl.removeAttribute('style')
    svgEl.setAttribute('width', '100%')
    svgEl.setAttribute('height', '100%')
    svgEl.style.width = '100%'
    svgEl.style.height = '100%'
    svgEl.style.maxWidth = 'none'
    svgEl.style.maxHeight = 'none'
    svgEl.style.display = 'block'
  } catch (_) {
    // ignore
  }

  const svgPanZoom = await ensureSvgPanZoom()

  // 重新打开或 SVG 变化时，确保销毁旧实例，避免事件/状态叠加
  _destroyPanZoom()

  svgPanZoomInstance = svgPanZoom(svgEl, {
    zoomEnabled: true,
    controlIconsEnabled: false, // 工具条由我们自己控制
    fit: true,
    center: true,
    panEnabled: true,
    mouseWheelZoomEnabled: true,
    dblClickZoomEnabled: true,
    // 让滚轮缩放更顺滑；滚动穿透由我们在画布容器上统一拦截
    preventMouseEventsDefault: false,
    zoomScaleSensitivity: 0.22,
    minZoom: 0.2,
    maxZoom: 20
  })

  // 初次打开时显式校准一次视图
  try {
    svgPanZoomInstance.resize()
    svgPanZoomInstance.fit()
    svgPanZoomInstance.center()
  } catch (_) {
    // ignore
  }

  // 拦截滚轮默认滚动（只阻止滚动，不阻止 svg-pan-zoom 收到 wheel 事件做缩放）
  const canvasEl = rootRef.value?.querySelector?.('.mermaid-viewer-canvas')
  if (canvasEl && !onViewerWheel) {
    onViewerWheel = (evt) => {
      evt.preventDefault()
    }
    canvasEl.addEventListener('wheel', onViewerWheel, { passive: false, capture: true })
  }

  // 跟随聊天窗大小变化
  if (rootRef.value && !viewerResizeObserver) {
    viewerResizeObserver = new ResizeObserver(() => {
      if (!svgPanZoomInstance) return
      try {
        svgPanZoomInstance.resize()
        svgPanZoomInstance.fit()
        svgPanZoomInstance.center()
      } catch (_) {
        // ignore
      }
    })
    viewerResizeObserver.observe(rootRef.value)
  }

  // Esc 关闭预览
  if (!onViewerKeydown) {
    onViewerKeydown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        close()
      }
    }
    window.addEventListener('keydown', onViewerKeydown, true)
  }
}

function zoomIn() {
  try {
    svgPanZoomInstance?.zoomIn?.()
  } catch (_) {
    // ignore
  }
}

function zoomOut() {
  try {
    svgPanZoomInstance?.zoomOut?.()
  } catch (_) {
    // ignore
  }
}

function reset() {
  if (!svgPanZoomInstance) return
  try {
    svgPanZoomInstance.reset()
    svgPanZoomInstance.resize()
    svgPanZoomInstance.fit()
    svgPanZoomInstance.center()
  } catch (_) {
    // ignore
  }
}

async function copySource() {
  if (!props.source) return

  const ok = await copyTextToClipboard(props.source)
  if (!ok) return

  viewerCopiedSource.value = true
  if (copiedSourceTimer) clearTimeout(copiedSourceTimer)
  copiedSourceTimer = setTimeout(() => {
    viewerCopiedSource.value = false
    copiedSourceTimer = null
  }, 1200)
}

function _getSvgStringForExport() {
  const svgEl = rootRef.value?.querySelector?.('.mermaid-viewer-canvas svg')
  if (!svgEl) return null

  // 深拷贝一份，避免污染页面中的 SVG（例如 svg-pan-zoom 注入的属性）
  const clone = svgEl.cloneNode(true)
  if (!(clone instanceof SVGElement)) return null

  clone.removeAttribute('style')
  // 保留 viewBox，但去掉宽高限制，交给导出逻辑决定
  clone.removeAttribute('width')
  clone.removeAttribute('height')
  clone.style.width = ''
  clone.style.height = ''
  clone.style.maxWidth = ''
  clone.style.maxHeight = ''

  // 导出稳定性：补充必要的命名空间
  if (!clone.getAttribute('xmlns')) {
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  }

  return new XMLSerializer().serializeToString(clone)
}

async function downloadImage() {
  const svgText = _getSvgStringForExport()
  if (!svgText) return

  const svgBlob = new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(svgBlob)

  try {
    const img = new Image()
    const loaded = new Promise((resolve, reject) => {
      img.onload = resolve
      img.onerror = reject
    })
    img.src = url
    await loaded

    // 导出 PNG 尺寸：取预览画布尺寸（用户看到的区域）
    const canvasEl = rootRef.value?.querySelector?.('.mermaid-viewer-canvas')
    const rect = canvasEl?.getBoundingClientRect?.()
    const w = Math.max(1, Math.floor(rect?.width || img.naturalWidth || img.width || 800))
    const h = Math.max(1, Math.floor(rect?.height || img.naturalHeight || img.height || 600))

    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // 使用当前主题背景色，避免透明 PNG 在不同底色下可读性差
    const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg-app')?.trim() || '#ffffff'
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, w, h)
    ctx.drawImage(img, 0, 0, w, h)

    const pngBlob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
    if (!pngBlob) return

    // 需求变更：不再“复制图片”，直接下载图片即可
    const dlUrl = URL.createObjectURL(pngBlob)
    const a = document.createElement('a')
    a.href = dlUrl
    a.download = 'mermaid.png'
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(dlUrl), 1000)

    viewerDownloadedImage.value = true
    if (downloadedImageTimer) clearTimeout(downloadedImageTimer)
    downloadedImageTimer = setTimeout(() => {
      viewerDownloadedImage.value = false
      downloadedImageTimer = null
    }, 1200)
  } finally {
    URL.revokeObjectURL(url)
  }
}

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) {
      cleanupViewer()
      return
    }
    _clearTimersAndFlags()
    await initPanZoomIfNeeded()
  }
)

watch(
  () => props.svgHtml,
  async () => {
    if (!props.open) return
    await initPanZoomIfNeeded()
  }
)

onUnmounted(() => {
  cleanupViewer()
})
</script>

<template>
  <div v-if="open" ref="rootRef" class="mermaid-viewer-overlay" @click.self="close">
    <div class="mermaid-viewer">
      <button class="mermaid-viewer-close" type="button" title="关闭 (Esc)" @click="close">
        <X :size="16" />
      </button>

      <div class="mermaid-viewer-canvas" v-html="svgHtml"></div>

      <div class="mermaid-viewer-toolbar" role="toolbar" aria-label="Mermaid 缩放工具">
        <button class="mermaid-toolbtn" type="button" data-tip="放大" @click="zoomIn">
          <ZoomIn :size="16" />
        </button>
        <button class="mermaid-toolbtn" type="button" data-tip="缩小" @click="zoomOut">
          <ZoomOut :size="16" />
        </button>
        <button class="mermaid-toolbtn" type="button" data-tip="重置" @click="reset">
          <RotateCcw :size="16" />
        </button>
        <div class="mermaid-tool-sep" aria-hidden="true"></div>
        <button
          class="mermaid-toolbtn"
          type="button"
          :data-tip="viewerCopiedSource ? '已复制 Mermaid 语句' : '复制 Mermaid 语句'"
          @click="copySource"
        >
          <Check v-if="viewerCopiedSource" :size="16" />
          <FileCode v-else :size="16" />
        </button>
        <button
          class="mermaid-toolbtn"
          type="button"
          :data-tip="viewerDownloadedImage ? '已下载图片' : '下载图片'"
          @click="downloadImage"
        >
          <Check v-if="viewerDownloadedImage" :size="16" />
          <ImageDown v-else :size="16" />
        </button>
      </div>
    </div>
  </div>
</template>


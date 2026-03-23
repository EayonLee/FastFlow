<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { Bot, Bug, MessageSquare, Send, Copy, Check } from 'lucide-vue-next'
import { useDraggable, useStorage, useWindowSize } from '@vueuse/core'
import FlowSelect from '@/shared/components/FlowSelect.vue'
import Header from '@/shared/components/Header.vue'
import MermaidViewer from '@/apps/chatbox/components/MermaidViewer.vue'
import AgentExecutionTimeline from '@/apps/chatbox/components/AgentExecutionTimeline.vue'
import AgentAnswerContent from '@/apps/chatbox/components/AgentAnswerContent.vue'
import AgentThinkingPanel from '@/apps/chatbox/components/AgentThinkingPanel.vue'
import ProtocolComposer from '@/apps/chatbox/components/ProtocolComposer.vue'
import { useCopyFeedback } from '@/shared/composables/useCopyFeedback.js'
import { DEFAULT_MIN_HEIGHT, DEFAULT_MIN_WIDTH, useResizable } from '@/shared/composables/useResizable.js'
import { useStreamTypewriter } from '@/shared/composables/useStreamTypewriter.js'
import { Bridge } from '@/extension/runtime/bridge.js'
import { Nexus } from '@/shared/services/nexus.js'
import { createAuthGuard } from '@/shared/utils/authGuard.js'
import { getModelConfigs } from '@/shared/services/modelConfig.js'
import { Layout } from '@/shared/utils/layout.js'
import { formatDateTime } from '@/shared/utils/time.js'
import { renderMarkdown } from '@/shared/utils/markdown.js'
import { getMermaidSourceByKey, renderMermaidInElement, renderMermaidSource } from '@/shared/utils/mermaid.js'
import { generateUuid32 } from '@/shared/utils/uuid.js'
import { useMermaidThemeSync } from '@/apps/chatbox/composables/useMermaidThemeSync.js'
import { splitProtocolText } from '@/apps/chatbox/protocols/parser.js'
import { themeManager } from '@/shared/utils/themeManager.js'

// 存储 key（用于记住聊天框尺寸）
const CHAT_SIZE_STORAGE_KEY = 'chat_box_size'
// 存储 key（用于记住悬浮球吸附位置，按站点 origin 隔离）
const ANCHOR_STORAGE_KEY = `chat_floating_anchor_v1::${window.location.origin}`
// 交互常量
const FLOAT_MARGIN = 16
const FLOAT_BUTTON_SIZE = 50
const FLOAT_PANEL_GAP = 12
const FLOAT_PANEL_MARGIN = 16
const DEFAULT_PANEL_WIDTH = 700
// 点击与拖拽判定阈值（像素）：小于该位移按点击处理，避免误触发拖拽
const DRAG_ACTIVATION_THRESHOLD = 6
// 默认欢迎语
const WELCOME_MESSAGE = 'Hi！👋\n' +
    '我是 Nexus，FastFlow 工作流智能助手，可以随时帮你优化或讲解工作流。\n\n' +
    '😎需要我帮你做什么？'
/**
 * 聊天视图组件
 * 作用：处理与用户的聊天交互、工作流生成和渲染请求。
 * 包含：
 * 1. 聊天窗口的开关状态管理
 * 2. 消息列表的展示与滚动
 * 3. 这里的逻辑是从 App.vue 拆分出来的，为了模块化。
 */

// 聊天窗口展开状态
const isOpen = ref(false)
// 输入框序列化后的用户文本（包含 selected_skill(...) / selected_node(...) 协议）
const composerPrompt = ref('')
// 登录状态（未登录时隐藏小球和聊天框）
const isAuthed = ref(false)
let authGuard = null

// 下拉菜单状态：当前选中的智能体与模型
const selectedAgent = ref('chat')
const selectedModel = ref('')

// 可选智能体列表
const agents = [
  { id: 'chat', label: 'Deep Chat', icon: MessageSquare, color: '#00ff41' },
  { id: 'builder', label: 'SOLO Builder', icon: Bot, color: '#c084fc' },
  { id: 'debug', label: 'SOLO Debugger', icon: Bug, color: '#f59e0b' }
]

// 可选模型列表（由后端配置拉取）
const models = ref([])
const isModelLoading = ref(false)

// 消息列表（包含系统欢迎语）
const messages = ref([
  { 
    id: generateUuid32(),
    type: 'ai', 
    content: WELCOME_MESSAGE,
    timestamp: formatDateTime(new Date())
  }
])
// 复制反馈逻辑（控制复制按钮图标切换）
const { copiedMap, copyText } = useCopyFeedback()
// 是否处于发送中（控制按钮禁用与加载动画）
const isLoading = ref(false)
// 消息容器 DOM 引用，用于滚动到末尾
const messagesContainer = ref(null)
// 输入组件引用（用于聚焦/清空）
const protocolComposerRef = ref(null)
// 聊天容器 DOM 引用，用于拖拽调整尺寸
const containerRef = ref(null)
// 悬浮球 DOM 引用（交由 VueUse useDraggable 管理）
const toggleButtonRef = ref(null)

// 视窗尺寸（响应式）
const { width: viewportWidth, height: viewportHeight } = useWindowSize()

// 默认锚点（右下角），top 表示小球 top 像素
const defaultAnchorTop = Math.max(FLOAT_MARGIN, window.innerHeight - FLOAT_BUTTON_SIZE - FLOAT_MARGIN)
const anchor = useStorage(
  ANCHOR_STORAGE_KEY,
  { side: 'right', top: defaultAnchorTop },
  window.localStorage,
  { mergeDefaults: true }
)
// 记录拖拽起点，用于区分“点击打开”和“拖拽移动”
const dragStartPoint = ref({ x: 0, y: 0 })
const dragActivated = ref(false)
const suppressNextToggleClick = ref(false)

function getBubbleSize() {
  return toggleButtonRef.value?.offsetWidth || FLOAT_BUTTON_SIZE
}

function clampBubbleX(x) {
  const size = getBubbleSize()
  const minX = FLOAT_MARGIN
  const maxX = Math.max(minX, viewportWidth.value - size - FLOAT_MARGIN)
  return Math.min(maxX, Math.max(minX, x))
}

function clampBubbleY(y) {
  const size = getBubbleSize()
  const minY = FLOAT_MARGIN
  const maxY = Math.max(minY, viewportHeight.value - size - FLOAT_MARGIN)
  return Math.min(maxY, Math.max(minY, y))
}

function getAnchorXBySide(side) {
  const size = getBubbleSize()
  if (side === 'left') return FLOAT_MARGIN
  return Math.max(FLOAT_MARGIN, viewportWidth.value - size - FLOAT_MARGIN)
}

function normalizeAnchor() {
  const currentSide = anchor.value?.side === 'left' ? 'left' : 'right'
  const currentTop = Number.isFinite(anchor.value?.top) ? anchor.value.top : defaultAnchorTop
  anchor.value = {
    side: currentSide,
    top: clampBubbleY(currentTop)
  }
}

function syncBubbleToAnchor() {
  bubbleX.value = clampBubbleX(getAnchorXBySide(anchor.value.side))
  bubbleY.value = clampBubbleY(anchor.value.top)
}

function snapAnchor(position) {
  const clampedX = clampBubbleX(position.x)
  const clampedY = clampBubbleY(position.y)
  const side = clampedX + getBubbleSize() / 2 <= viewportWidth.value / 2 ? 'left' : 'right'
  anchor.value = {
    side,
    top: clampedY
  }
  syncBubbleToAnchor()
}

const {
  x: bubbleX,
  y: bubbleY,
  isDragging: isBubbleDragging
} = useDraggable(toggleButtonRef, {
  initialValue: {
    x: getAnchorXBySide(anchor.value.side),
    y: anchor.value.top
  },
  preventDefault: true,
  stopPropagation: true,
  onStart(position) {
    dragStartPoint.value = { x: position.x, y: position.y }
    dragActivated.value = false
    suppressNextToggleClick.value = false
  },
  onMove(position) {
    // 先做“点击/拖拽”判定：未达到阈值前不移动小球，避免点击时轻微抖动造成漂移。
    if (!dragActivated.value) {
      const dx = Math.abs(position.x - dragStartPoint.value.x)
      const dy = Math.abs(position.y - dragStartPoint.value.y)
      if (dx < DRAG_ACTIVATION_THRESHOLD && dy < DRAG_ACTIVATION_THRESHOLD) {
        return
      }
      dragActivated.value = true
      if (!suppressNextToggleClick.value) {
        suppressNextToggleClick.value = true
      }
    }
    bubbleX.value = clampBubbleX(position.x)
    bubbleY.value = clampBubbleY(position.y)
  },
  onEnd(position) {
    // 未激活拖拽表示本次是“点击”，不更新锚点，保持位置稳定。
    if (!dragActivated.value) return
    snapAnchor(position)
  }
})

const toggleButtonStyle = computed(() => {
  if (isBubbleDragging.value) {
    return {
      left: `${clampBubbleX(bubbleX.value)}px`,
      top: `${clampBubbleY(bubbleY.value)}px`,
      right: 'auto',
      bottom: 'auto'
    }
  }

  return {
    left: `${getAnchorXBySide(anchor.value.side)}px`,
    top: `${clampBubbleY(anchor.value.top)}px`,
    right: 'auto',
    bottom: 'auto'
  }
})

function getDefaultPanelHeight() {
  return Math.min(900, Math.max(DEFAULT_MIN_HEIGHT, viewportHeight.value - 60))
}

const panelWidth = ref(DEFAULT_PANEL_WIDTH)
const panelHeight = ref(getDefaultPanelHeight())
const panelBottomOffset = ref(0)
const activeResizeRect = ref(null)

function clampPanelDimension(value, preferredMin, max) {
  const safeMax = Math.max(0, max)
  const safeMin = Math.min(preferredMin, safeMax)
  return Math.min(safeMax, Math.max(safeMin, value))
}

function getBubbleMetrics() {
  const bubbleTop = clampBubbleY(anchor.value.top)
  const bubbleSize = getBubbleSize()
  const bubbleLeft = getAnchorXBySide(anchor.value.side)
  return {
    bubbleLeft,
    bubbleSize,
    bubbleTop,
    bubbleBottom: bubbleTop + bubbleSize
  }
}

function getPanelMaxWidth(side, bubbleLeft, bubbleSize) {
  if (side === 'left') {
    const fixedLeft = bubbleLeft + bubbleSize + FLOAT_PANEL_GAP
    return viewportWidth.value - FLOAT_PANEL_MARGIN - fixedLeft
  }
  const fixedRight = bubbleLeft - FLOAT_PANEL_GAP
  return fixedRight - FLOAT_PANEL_MARGIN
}

function buildIdlePanelRect(width = panelWidth.value, height = panelHeight.value, bottomOffset = panelBottomOffset.value) {
  const { bubbleLeft, bubbleSize, bubbleBottom } = getBubbleMetrics()
  const maxWidth = getPanelMaxWidth(anchor.value.side, bubbleLeft, bubbleSize)
  const safeWidth = clampPanelDimension(width, DEFAULT_MIN_WIDTH, maxWidth)
  const maxHeight = viewportHeight.value - (FLOAT_PANEL_MARGIN * 2)
  const safeHeight = clampPanelDimension(height, DEFAULT_MIN_HEIGHT, maxHeight)
  const preferredBottom = bubbleBottom + bottomOffset
  const minBottom = FLOAT_PANEL_MARGIN + safeHeight
  const maxBottom = viewportHeight.value - FLOAT_PANEL_MARGIN
  const bottom = Math.min(maxBottom, Math.max(minBottom, preferredBottom))
  const top = bottom - safeHeight

  if (anchor.value.side === 'left') {
    const left = bubbleLeft + bubbleSize + FLOAT_PANEL_GAP
    return {
      left,
      top,
      width: safeWidth,
      height: safeHeight,
      right: left + safeWidth,
      bottom
    }
  }

  const right = bubbleLeft - FLOAT_PANEL_GAP
  return {
    left: right - safeWidth,
    top,
    width: safeWidth,
    height: safeHeight,
    right,
    bottom
  }
}

function syncPanelGeometryToViewport() {
  const rect = buildIdlePanelRect()
  const { bubbleBottom } = getBubbleMetrics()
  panelWidth.value = rect.width
  panelHeight.value = rect.height
  panelBottomOffset.value = rect.bottom - bubbleBottom
  return rect
}

const chatContainerStyle = computed(() => {
  const rect = activeResizeRect.value ?? buildIdlePanelRect()
  return {
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    right: 'auto',
    bottom: 'auto'
  }
})

// 主题切换时让已渲染 Mermaid 图同步换色（避免“背景切了但图还是旧主题”）
useMermaidThemeSync(messagesContainer)
// 会话 ID（用于后端上下文与连续对话）
const sessionId = ref(generateUuid32())
// 是否正在拖拽尺寸（用于样式表现）
const isResizing = ref(false)
// 拖拽尺寸逻辑（含缓存）
const resizer = useResizable({
  edgePadding: FLOAT_PANEL_MARGIN,
  minHeight: DEFAULT_MIN_HEIGHT,
  minWidth: DEFAULT_MIN_WIDTH,
  onResizeStateChange: (val) => {
    isResizing.value = val
  },
  onResize: (rect) => {
    activeResizeRect.value = rect
  },
  onResizeEnd: (rect, meta) => {
    const { bubbleBottom } = getBubbleMetrics()
    activeResizeRect.value = null
    panelWidth.value = rect.width
    panelHeight.value = rect.height
    if (meta.dir.includes('s')) {
      panelBottomOffset.value = rect.bottom - bubbleBottom
    }
    syncPanelGeometryToViewport()
  },
  // 聊天框大小缓存key
  storageKey: CHAT_SIZE_STORAGE_KEY
})

function getCurrentPanelRect() {
  return activeResizeRect.value ?? buildIdlePanelRect()
}

function handleResizeStart(dir, event) {
  resizer.startResize(dir, event, {
    anchorSide: anchor.value.side,
    rect: getCurrentPanelRect()
  })
}

// 流式打字机渲染（将 chunk 按字符节奏展示）
const streamTypewriter = useStreamTypewriter({
  charsPerTick: 1,
  intervalMs: 16,
  flushOnHidden: true,
  onText: (id, text) => {
    updateMessage(id, (target) => {
      if (target.isLoading) target.isLoading = false
      target.content = `${target.content || ''}${text}`
    })
    scrollToBottom()
  }
})

// Mermaid 放大查看（拖拽 + 缩放）
const mermaidViewerOpen = ref(false)
const mermaidViewerSvg = ref('')
const mermaidViewerSource = ref('')
let unsubscribeViewerTheme = null
let viewerThemeScheduled = false

function closeMermaidViewer() {
  mermaidViewerOpen.value = false
  mermaidViewerSvg.value = ''
  mermaidViewerSource.value = ''
}

function openMermaidViewer(svgHtml) {
  mermaidViewerSvg.value = svgHtml || ''
  mermaidViewerOpen.value = true
}

function scheduleViewerRerender() {
  if (viewerThemeScheduled) return
  viewerThemeScheduled = true
  queueMicrotask(async () => {
    viewerThemeScheduled = false
    if (!mermaidViewerOpen.value) return
    const src = String(mermaidViewerSource.value || '').trim()
    if (!src) return
    const svg = await renderMermaidSource(src)
    if (!svg) return
    // 替换 SVG 后 MermaidViewer 内部会重新初始化 svg-pan-zoom
    mermaidViewerSvg.value = svg
  })
}

function markRuntimeCompleted(messageId) {
  if (!messageId) return
  updateMessage(messageId, (target) => {
    target.runtimeCompleted = true
    if (target.runtimeStatus !== 'failed') {
      target.runtimeStatus = 'completed'
    }
  })
}

// 创建消息对象（统一时间格式）
function createMessage(content, type, extra = {}) {
  const base = {
    id: generateUuid32(),
    type,
    content,
    timestamp: formatDateTime(new Date()),
    executionEvents: type === 'ai' ? [] : undefined,
    thinkingContent: type === 'ai' ? '' : undefined,
    executionPanelOpen: type === 'ai' ? false : undefined,
    thinkingPanelOpen: type === 'ai' ? false : undefined,
    runtimeCompleted: type === 'ai' ? false : undefined,
    runtimeStatus: type === 'ai' ? 'running' : undefined
  }
  return { ...base, ...extra }
}

// 根据消息 ID 查找消息对象
function findMessage(id) {
  return messages.value.find(m => m.id === id)
}

// 统一更新消息内容（可选更新 loading）
function updateMessage(id, updater) {
  const target = findMessage(id)
  if (!target) return null
  updater(target)
  return target
}

// 写入错误消息并滚动到底部
function setMessageError(id, message) {
  // 出错时先清理该消息未输出完的流式队列
  streamTypewriter.clear(id)
  updateMessage(id, (target) => {
    target.isLoading = false
    target.content = message
    target.runtimeCompleted = true
    target.runtimeStatus = 'failed'
  })
  scrollToBottom()
}

// 将流式文本追加到指定消息
function appendChunkToMessage(id, chunk) {
  if (!chunk) return
  // 浏览器后台标签页会对定时器强节流：隐藏时直接输出，避免“看起来不继续”。
  if (document.visibilityState === 'hidden') {
    streamTypewriter.flush(id)
    updateMessage(id, (target) => {
      if (target.isLoading) target.isLoading = false
      target.content = `${target.content || ''}${chunk}`
    })
    scrollToBottom()
    return
  }
  streamTypewriter.enqueue(id, chunk)
}

function appendExecutionEvent(id, event) {
  if (!event || !event.type) return
  updateMessage(id, (target) => {
    if (!Array.isArray(target.executionEvents)) target.executionEvents = []
    target.executionEvents.push({
      id: `${target.executionEvents.length + 1}-${Date.now()}`,
      type: event.type,
      message: event.message || '',
      toolName: event.tool_name || '',
      status: event.status || '',
      elapsedMs: Number.isFinite(event.elapsed_ms) ? event.elapsed_ms : null,
      ts: event.ts || ''
    })
  })
  scrollToBottom()
}

function appendThinkingContent(id, text, mode = 'append') {
  if (!text) return
  updateMessage(id, (target) => {
    const current = String(target.thinkingContent || '')
    if (mode === 'replace') {
      target.thinkingContent = text
      return
    }
    target.thinkingContent = `${current}${text}`
  })
  scrollToBottom()
}

onMounted(async () => {
  // 初始化登录态守卫（未登录时隐藏小球与聊天框）
  authGuard = createAuthGuard({
    onAuthedChange: (val) => {
      isAuthed.value = val
      if (!val) {
        isOpen.value = false
      }
    }
  })
  await authGuard.start()

  // 主题切换时：如果 Mermaid 放大预览打开，则按新主题重渲染预览图
  await themeManager.ready
  unsubscribeViewerTheme = themeManager.subscribe(() => {
    scheduleViewerRerender()
  })
})

onUnmounted(() => {
  // 清理登录态守卫与拖拽事件
  if (authGuard) {
    authGuard.stop()
    authGuard = null
  }
  // 清理流式打字机定时器
  streamTypewriter.cleanup()
  resizer.cleanup()
  if (mermaidRenderTimer) {
    clearTimeout(mermaidRenderTimer)
    mermaidRenderTimer = null
  }

  if (unsubscribeViewerTheme) {
    unsubscribeViewerTheme()
    unsubscribeViewerTheme = null
  }

  closeMermaidViewer()
})

watch(isAuthed, async (val) => {
  // 未登录：强制关闭聊天框
  if (!val) {
    isOpen.value = false
    return
  }
  // 登录后：加载模型配置并恢复尺寸
  loadModelConfigs()
  await nextTick()
  normalizeAnchor()
  syncBubbleToAnchor()
  const restoredSize = await resizer.restoreSize()
  if (restoredSize) {
    panelWidth.value = restoredSize.width
    panelHeight.value = restoredSize.height
  } else {
    panelWidth.value = DEFAULT_PANEL_WIDTH
    panelHeight.value = getDefaultPanelHeight()
  }
  panelBottomOffset.value = 0
  syncPanelGeometryToViewport()
})

watch([viewportWidth, viewportHeight], () => {
  normalizeAnchor()
  if (!isBubbleDragging.value) {
    syncBubbleToAnchor()
  }
  if (!isResizing.value) {
    syncPanelGeometryToViewport()
  }
})

watch(
  [() => anchor.value.side, () => anchor.value.top],
  () => {
    if (!isResizing.value) {
      syncPanelGeometryToViewport()
    }
  }
)

// 拉取模型配置并设置默认模型
async function loadModelConfigs() {
  if (isModelLoading.value) return
  isModelLoading.value = true
  try {
    const configs = await getModelConfigs()
    models.value = (configs || []).map((cfg) => ({
      id: cfg.id,
      label: cfg.modelName || cfg.modelId || `Model ${cfg.id}`
    }))
    if (!selectedModel.value && models.value.length > 0) {
      selectedModel.value = models.value[0].id
    }
  } finally {
    isModelLoading.value = false
  }
}

// 切换聊天窗口显示状态
function toggleChat() {
  // 拖拽结束后的“幽灵点击”直接吞掉，避免误打开
  if (suppressNextToggleClick.value) {
    suppressNextToggleClick.value = false
    return
  }
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    // 展开时滚动到底部并聚焦输入框
    nextTick(() => {
      scrollToBottom()
      protocolComposerRef.value?.focusEditor?.()
    })
  }
}

// 关闭聊天窗口
function closeChat() {
  isOpen.value = false
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      // 强制设置 scrollTop 为 scrollHeight，确保滚动到最底部
      // 平滑滚动有时候因为内容还在渲染中（例如图片加载或动画）导致计算不准，这里直接跳到最底部
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

let mermaidRenderTimer = null
function renderMermaidOnceAfterReply() {
  if (mermaidRenderTimer) return
  mermaidRenderTimer = setTimeout(() => {
    mermaidRenderTimer = null
    nextTick(() => {
      if (!messagesContainer.value) return
      renderMermaidInElement(messagesContainer.value)
    })
  }, 80)
}

function renderMermaidNow() {
  nextTick(() => {
    if (!messagesContainer.value) return
    renderMermaidInElement(messagesContainer.value)
  })
}

function handleMessagesClick(e) {
  const path = typeof e?.composedPath === 'function' ? e.composedPath() : []
  const fromPath = path.find((el) => el && el.classList && el.classList.contains('msg-mermaid'))
  const target = e?.target
  const mermaidBlock = fromPath || target?.closest?.('.msg-mermaid')
  if (!mermaidBlock) return

  // 只支持“内联 SVG”的图放大；如果是 iframe（sandbox 输出），这里会找不到 svg。
  const svgEl = mermaidBlock.querySelector?.('svg')
  if (!svgEl) return

  const key = mermaidBlock.getAttribute?.('data-key') || ''
  mermaidViewerSource.value = getMermaidSourceByKey(key) || ''

  openMermaidViewer(svgEl.outerHTML)
}

// 添加消息辅助函数
function addMessage(content, type, extra = {}) {
  messages.value.push(createMessage(content, type, extra))
  scrollToBottom()
}

// 复制消息内容到剪贴板
async function copyMessage(content, messageId) {
  await copyText(content, messageId)
}

// 将消息文本渲染为 HTML（支持基础 Markdown）
function renderMessageContent(content) {
  return renderMarkdown(content || '')
}

function renderUserMessageSegments(message) {
  if (Array.isArray(message?.displaySegments) && message.displaySegments.length > 0) {
    return message.displaySegments
  }
  return splitProtocolText(message?.content || '')
}

function shouldShowRuntimePanels(message) {
  if (!message || message.type !== 'ai') return false
  if (message.isLoading) return true
  if (message.runtimeCompleted) return true
  if (Array.isArray(message.executionEvents) && message.executionEvents.length > 0) return true
  return !!String(message.thinkingContent || '').trim()
}

function handleSlashTrigger() {
  protocolComposerRef.value?.triggerSlashFromButton?.()
}

function handleHashTrigger() {
  protocolComposerRef.value?.triggerHashFromButton?.()
}

function getComposerSnapshot() {
  const snapshot = protocolComposerRef.value?.buildSnapshot?.()
  if (snapshot && typeof snapshot === 'object') {
    const prompt = String(snapshot.prompt || '')
    const displaySegments = Array.isArray(snapshot.displaySegments)
      ? snapshot.displaySegments
      : splitProtocolText(prompt)
    return { prompt, displaySegments }
  }
  const prompt = String(composerPrompt.value || '')
  return {
    prompt,
    displaySegments: splitProtocolText(prompt),
  }
}

// 发送消息处理逻辑
async function handleGenerate() {
  if (isLoading.value) return
  // 1) 校验输入
  const snapshot = getComposerSnapshot()
  const prompt = snapshot.prompt.trim()
  if (!prompt) return
  const isChatAgent = selectedAgent.value === 'chat'

  // 2) Chat 模式需要模型配置；Builder / Debug 统一交由 Nexus 返回禁用态消息。
  if (isChatAgent && !selectedModel.value) {
    addMessage('当前没有可用的模型配置，请先在系统中配置模型。', 'ai')
    return
  }

  // 3) 添加用户消息
  const displaySegments = Array.isArray(snapshot.displaySegments)
    ? snapshot.displaySegments.map((segment) => ({ ...segment }))
    : splitProtocolText(prompt)
  addMessage(prompt, 'user', { displaySegments })
  protocolComposerRef.value?.clear?.()
  composerPrompt.value = ''
  isLoading.value = true

  // 4) 显示加载中消息（用于流式更新）
  const loadingMsgId = generateUuid32() // 使用 32 位 UUID，避免冲突
  messages.value.push(
    createMessage('', 'ai', {
      id: loadingMsgId,
      isLoading: true,
      executionEvents: [
        {
          id: `boot-${Date.now()}`,
          type: 'phase.started',
          message: '等待智能体处理用户问题',
          status: 'running',
          elapsedMs: null,
          ts: ''
        }
      ]
    })
  )
  scrollToBottom()

  let chatRequestFinalized = false
  const finalizeChatRequest = () => {
    if (!isChatAgent || chatRequestFinalized) return
    chatRequestFinalized = true
    streamTypewriter.drain(loadingMsgId).then(() => {
      updateMessage(loadingMsgId, (target) => {
        if (target.isLoading) target.isLoading = false
      })
      markRuntimeCompleted(loadingMsgId)
      renderMermaidOnceAfterReply()
      isLoading.value = false
    })
  }

  // 5) 仅 Chat 模式需要导出当前工作流配置与元信息。
  let workflowGraph = null
  let workflowMeta = null
  if (isChatAgent) {
    try {
      workflowGraph = await Bridge.exportWorkflowGraph()
      try {
        workflowMeta = await Bridge.exportWorkflowMeta()
      } catch (metaErr) {
        console.warn('[FastFlow] Export workflow meta failed:', metaErr)
        workflowMeta = null
      }
    } catch (e) {
      setMessageError(loadingMsgId, `Export current workflow graph failed：${e.message}`)
      // 终止本次发送
      isLoading.value = false
      return
    }
  }

  // 6) 调用 Nexus（SSE 流式）
  Nexus.generateWorkflow(
    {
      // 请求参数：prompt + 选中的 agent + 模型 + 会话 + 当前画布
      prompt,
      mode: selectedAgent.value,
      modelConfigId: isChatAgent ? selectedModel.value : null,
      sessionId: sessionId.value,
      workflowGraph,
      workflowMeta
    },
    (event) => {
      if (!event || !event.type) return
      if (event.type === 'answer.delta') {
        appendChunkToMessage(loadingMsgId, event.content || '')
        return
      }
      if (event.type === 'answer.done') {
        finalizeChatRequest()
        return
      }
      if (event.type === 'answer.reset') {
        streamTypewriter.clear(loadingMsgId)
        updateMessage(loadingMsgId, (target) => {
          target.content = ''
        })
        appendExecutionEvent(loadingMsgId, event)
        return
      }
      if (event.type === 'thinking.delta') {
        appendThinkingContent(loadingMsgId, event.content || '', 'append')
        return
      }
      if (event.type === 'thinking.summary') {
        appendThinkingContent(loadingMsgId, event.content || '', 'replace')
        return
      }
      appendExecutionEvent(loadingMsgId, event)
      if (event.type === 'run.completed') {
        finalizeChatRequest()
      }
    },
    (graphData) => {
      // Chat 智能体不返回图，直接结束
      if (isChatAgent) {
        finalizeChatRequest()
        return
      }

      // Builder 成功回调 - 更新同一条消息
      const targetMsg = findMessage(loadingMsgId)
      if (targetMsg) {
        // Builder 成功后清理流式队列，防止旧文本继续追加
        streamTypewriter.clear(loadingMsgId)
        targetMsg.isLoading = false
        targetMsg.content = `✅ 生成成功！包含 ${graphData.nodes.length} 个节点。正在排版...`
        // 内容更新后，重新滚动到底部
        scrollToBottom()
      }
      
      try {
        // 应用 Dagre 布局算法
        const layoutedGraph = Layout.applyDagre(graphData)
        
        // 发送渲染请求给页面
        Bridge.sendRenderRequest(
          layoutedGraph,
          () => {
            if (targetMsg) {
              // 渲染成功提示
              targetMsg.content = '🎉 新画布渲染成功！'
              scrollToBottom()
            }
            renderMermaidNow()
            isLoading.value = false
          },
          () => {
            // 失败回调：仅提示错误，不做降级方案
            if (targetMsg) {
              // 渲染失败提示
              targetMsg.content = '新画布渲染失败：未能将编排应用到页面，请检查页面是否处于可编辑状态。'
              scrollToBottom()
            }
            isLoading.value = false
          }
        )
      } catch (e) {
        if (targetMsg) {
          // 布局或渲染过程中异常
          targetMsg.isLoading = false
          targetMsg.content = `Formatting or Rendering Error: \n${e.message}`
        }
        isLoading.value = false
      }
    },
    (error) => {
      // 错误回调 - 更新同一条消息
      setMessageError(loadingMsgId, `${error.message}`)
      isLoading.value = false
    }
  )
}
</script>

<template>
  <div class="chat-view">
    <!-- 悬浮开关按钮 -->
    <div 
      v-if="isAuthed"
      v-show="!isOpen"
      id="fastflow-toggle-btn"
      ref="toggleButtonRef"
      :class="[{ dragging: isBubbleDragging }]"
      :style="toggleButtonStyle"
      @click="toggleChat"
    >
      <MessageSquare size="24" />
    </div>

    <!-- 聊天容器 -->
    <div 
      v-if="isAuthed"
      id="fastflow-copilot-container" 
      :class="{
        active: isOpen,
        resizing: isResizing,
        'mermaid-viewer-open': mermaidViewerOpen,
        'anchor-left': anchor.side === 'left',
        'anchor-right': anchor.side === 'right'
      }"
      :style="chatContainerStyle"
      ref="containerRef"
    >
      <div class="chat-main-interface">
        <!-- 公共 Header -->
        <Header 
          show-close 
          @close="closeChat"
        />
        
        <!-- 消息区域 -->
        <div class="messages-area" ref="messagesContainer" @click="handleMessagesClick">
          <div 
            v-for="msg in messages" 
            :key="msg.id" 
            class="message-wrapper" 
            :class="[
              msg.type,
              {
                'has-runtime-details': msg.type === 'ai' && (
                  (Array.isArray(msg.executionEvents) && msg.executionEvents.length > 0) ||
                  String(msg.thinkingContent || '').trim()
                )
              }
            ]"
          >
            <div class="message-content-box">
              <div class="msg-header">
                <span class="role-name">{{ msg.type === 'user' ? 'You' : 'NEXUS' }}</span>
                <span class="msg-time">{{ msg.timestamp }}</span>
              </div>
              <AgentExecutionTimeline
                v-if="shouldShowRuntimePanels(msg)"
                :events="Array.isArray(msg.executionEvents) ? msg.executionEvents : []"
                :open="msg.executionPanelOpen !== false"
                :completed="!!msg.runtimeCompleted"
                :runtime-status="String(msg.runtimeStatus || '')"
              />
              <AgentThinkingPanel
                v-if="shouldShowRuntimePanels(msg)"
                :content="String(msg.thinkingContent || '')"
                :open="msg.thinkingPanelOpen !== false"
                :completed="!!msg.runtimeCompleted"
                :runtime-status="String(msg.runtimeStatus || '')"
                :placeholder="shouldShowRuntimePanels(msg)"
              />
              <div
                v-if="msg.type === 'user'"
                class="msg-body user-protocol-body"
              >
                <template v-for="(segment, idx) in renderUserMessageSegments(msg)" :key="`${msg.id}-${idx}`">
                  <span v-if="segment.type === 'skill'" class="msg-skill-chip">{{ segment.name }}</span>
                  <span v-else-if="segment.type === 'node'" class="msg-node-chip">{{ segment.label || segment.node_id }}</span>
                  <span v-else>{{ segment.text }}</span>
                </template>
                <button 
                  v-if="!msg.isLoading && msg.content" 
                  class="copy-btn copy-btn-bubble" 
                  @click="copyMessage(msg.content, msg.id)"
                  title="复制内容"
                >
                  <Check v-if="copiedMap.get(msg.id)" size="12" />
                  <Copy v-else size="12" />
                </button>
              </div>
              <AgentAnswerContent
                v-else
                :is-loading="!!msg.isLoading"
                :content-html="renderMessageContent(msg.content)"
                :show-copy="!msg.isLoading && !!msg.content"
                :copied="!!copiedMap.get(msg.id)"
                @copy="copyMessage(msg.content, msg.id)"
              />
            </div>
          </div>
    </div>

        <MermaidViewer
          :open="mermaidViewerOpen"
          :svg-html="mermaidViewerSvg"
          :source="mermaidViewerSource"
          @close="closeMermaidViewer"
        />
        
        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-wrapper">
            <ProtocolComposer
              ref="protocolComposerRef"
              v-model="composerPrompt"
              :can-submit="!isLoading"
              placeholder="有问题，尽管问"
              @submit="handleGenerate"
            />
            
            <div class="input-footer">
              <div class="left-controls">
                <!-- Agent 选择器 -->
                <FlowSelect 
                  v-model="selectedAgent" 
                  :options="agents" 
                  width="auto"
                  min-width="120px"
                  position="top"
                />
                <button
                  type="button"
                  class="slash-trigger-btn"
                  data-protocol-trigger-btn="1"
                  title="插入 / 并打开技能面板"
                  @click="handleSlashTrigger"
                >
                  /
                </button>
                <button
                  type="button"
                  class="slash-trigger-btn"
                  data-protocol-trigger-btn="1"
                  title="插入 # 并打开节点面板"
                  @click="handleHashTrigger"
                >
                  #
                </button>
              </div>

              <div class="right-controls">
                <!-- 模型选择器 -->
                <FlowSelect 
                  v-model="selectedModel" 
                  :options="models" 
                  width="auto"
                  min-width="90px"
                  position="top"
                />

                <!-- 发送按钮 -->
                <button 
                  id="fastflow-send-btn"
                  class="send-btn" 
                  :disabled="!composerPrompt.trim() || isLoading"
                  @click="handleGenerate"
                >
                  <Send size="16" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="resize-handle nw" @pointerdown="handleResizeStart('nw', $event)"></div>
      <div class="resize-handle ne" @pointerdown="handleResizeStart('ne', $event)"></div>
      <div class="resize-handle sw" @pointerdown="handleResizeStart('sw', $event)"></div>
      <div class="resize-handle se" @pointerdown="handleResizeStart('se', $event)"></div>
    </div>
  </div>
</template>

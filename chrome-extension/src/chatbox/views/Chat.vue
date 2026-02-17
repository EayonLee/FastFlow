<script setup>
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { Bot, MessageSquare, Send, Copy, Check } from 'lucide-vue-next'
import FlowSelect from '@/components/FlowSelect.vue'
import Header from '@/components/Header.vue'
import MermaidViewer from '@/chatbox/components/MermaidViewer.vue'
import AgentExecutionTimeline from '@/chatbox/components/AgentExecutionTimeline.vue'
import AgentAnswerContent from '@/chatbox/components/AgentAnswerContent.vue'
import AgentThinkingPanel from '@/chatbox/components/AgentThinkingPanel.vue'
import { useCopyFeedback } from '@/composables/useCopyFeedback.js'
import { useResizable } from '@/composables/useResizable.js'
import { useStreamTypewriter } from '@/composables/useStreamTypewriter.js'
import { Bridge } from '@/services/bridge.js'
import { Nexus } from '@/services/nexus.js'
import { createAuthGuard } from '@/utils/authGuard.js'
import { getModelConfigs } from '@/services/modelConfig.js'
import { Layout } from '@/utils/layout.js'
import { formatDateTime } from '@/utils/time.js'
import { renderMarkdown } from '@/utils/markdown.js'
import { getMermaidSourceByKey, renderMermaidInElement, renderMermaidSource } from '@/utils/mermaid.js'
import { generateUuid32 } from '@/utils/uuid.js'
import { useMermaidThemeSync } from '@/chatbox/composables/useMermaidThemeSync.js'
import { themeManager } from '@/utils/themeManager.js'

// 存储 key（用于记住聊天框尺寸）
const CHAT_SIZE_STORAGE_KEY = 'chat_box_size'
// 默认欢迎语
const WELCOME_MESSAGE = 'Hi！👋\n' +
    '我是 Nexus，FastFlow 工作流智能助手，可以随时帮你优化或讲解工作流。\n\n' +
    '😎需要我帮你做什么？'
// 输入框行数约束
const MIN_INPUT_ROWS = 3
const MAX_INPUT_ROWS = 6

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
// 输入框内容
const inputValue = ref('')
// 输入框行数（默认 3 行，最多 6 行）
const inputRows = ref(MIN_INPUT_ROWS)
// 登录状态（未登录时隐藏小球和聊天框）
const isAuthed = ref(false)
let authGuard = null

// 下拉菜单状态：当前选中的智能体与模型
const selectedAgent = ref('chat')
const selectedModel = ref('')

// 可选智能体列表
const agents = [
  { id: 'chat', label: 'Chat', icon: MessageSquare, color: '#00ff41' },
  { id: 'builder', label: 'SOLO Builder', icon: Bot, color: '#c084fc' }
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
// 输入框 DOM 引用，用于展开时自动聚焦
const inputRef = ref(null)
// 聊天容器 DOM 引用，用于拖拽调整尺寸
const containerRef = ref(null)

// 主题切换时让已渲染 Mermaid 图同步换色（避免“背景切了但图还是旧主题”）
useMermaidThemeSync(messagesContainer)
// 会话 ID（用于后端上下文与连续对话）
const sessionId = ref(generateUuid32())
// 是否正在拖拽尺寸（用于样式表现）
const isResizing = ref(false)
// 拖拽尺寸逻辑（含缓存）
const resizer = useResizable(containerRef, {
  onResizeStateChange: (val) => {
    isResizing.value = val
  },
  // 聊天框大小缓存key
  storageKey: CHAT_SIZE_STORAGE_KEY
})

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
    runtimeCompleted: type === 'ai' ? false : undefined
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
  resizer.restoreSize()
})

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
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    // 展开时滚动到底部并聚焦输入框
    nextTick(() => {
      scrollToBottom()
      inputRef.value?.focus()
    })
  }
}

// 关闭聊天窗口
function closeChat() {
  isOpen.value = false
}

// 计算输入框行数（默认 3 行，最多 6 行）
function updateInputRows() {
  const value = inputValue.value || ''
  const lineCount = value.split('\n').length
  const nextRows = Math.max(MIN_INPUT_ROWS, Math.min(MAX_INPUT_ROWS, lineCount))
  if (inputRows.value !== nextRows) {
    inputRows.value = nextRows
  }
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
function addMessage(content, type) {
  messages.value.push(createMessage(content, type))
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

function shouldShowRuntimePanels(message) {
  if (!message || message.type !== 'ai') return false
  if (message.isLoading) return true
  if (message.runtimeCompleted) return true
  if (Array.isArray(message.executionEvents) && message.executionEvents.length > 0) return true
  return !!String(message.thinkingContent || '').trim()
}

// 发送消息处理逻辑
async function handleGenerate() {
  // 1) 校验输入
  const prompt = inputValue.value.trim()
  if (!prompt) return
  // 2) 校验模型配置
  if (!selectedModel.value) {
    addMessage('当前没有可用的模型配置，请先在系统中配置模型。', 'ai')
    return
  }

  // 3) 添加用户消息
  addMessage(prompt, 'user')
  inputValue.value = ''
  inputRows.value = MIN_INPUT_ROWS
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
          message: '等待模型分析用户问题',
          status: 'running',
          elapsedMs: null,
          ts: ''
        }
      ]
    })
  )
  scrollToBottom()

  const isChatAgent = selectedAgent.value === 'chat'
  // 5) 所有模式都导出当前工作流配置原文，并从 DOM 读取当前工作流名称/描述
  let workflowGraph = null
  let workflowMeta = null
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

  // 6) 调用 Nexus（SSE 流式）
  Nexus.generateWorkflow(
    {
      // 请求参数：prompt + 选中的 agent + 模型 + 会话 + 当前画布
      prompt,
      mode: selectedAgent.value,
      modelConfigId: selectedModel.value,
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
        markRuntimeCompleted(loadingMsgId)
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
        markRuntimeCompleted(loadingMsgId)
      }
    },
    (graphData) => {
      // Chat 智能体不返回图，直接结束
      if (isChatAgent) {
        // 等待所有 chunk 渲染完成后再结束 loading
        streamTypewriter.drain(loadingMsgId).then(() => {
          updateMessage(loadingMsgId, (target) => {
            if (target.isLoading) target.isLoading = false
          })
          markRuntimeCompleted(loadingMsgId)
          renderMermaidOnceAfterReply()
          isLoading.value = false
        })
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

// 键盘事件处理（Enter 发送）
function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    // 仅在非加载状态且有内容时发送
    if (!isLoading.value && inputValue.value.trim()) {
      handleGenerate()
    }
  }
}
</script>

<template>
  <div class="chat-view">
    <!-- 悬浮开关按钮 -->
    <div 
      v-if="isAuthed"
      v-show="!isOpen"
      id="fastflow-toggle-btn"
      @click="toggleChat"
    >
      <MessageSquare size="24" />
    </div>

    <!-- 聊天容器 -->
    <div 
      v-if="isAuthed"
      id="fastflow-copilot-container" 
      :class="{ active: isOpen, resizing: isResizing, 'mermaid-viewer-open': mermaidViewerOpen }"
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
                <button 
                  v-if="!msg.isLoading && msg.content" 
                  class="copy-btn" 
                  @click="copyMessage(msg.content, msg.id)"
                  title="复制内容"
                >
                  <Check v-if="copiedMap.get(msg.id)" size="12" />
                  <Copy v-else size="12" />
                </button>
              </div>
              <AgentExecutionTimeline
                v-if="shouldShowRuntimePanels(msg)"
                :events="Array.isArray(msg.executionEvents) ? msg.executionEvents : []"
                :open="msg.executionPanelOpen !== false"
                :completed="!!msg.runtimeCompleted"
              />
              <AgentThinkingPanel
                v-if="shouldShowRuntimePanels(msg)"
                :content="String(msg.thinkingContent || '')"
                :open="msg.thinkingPanelOpen !== false"
                :completed="!!msg.runtimeCompleted"
                :placeholder="shouldShowRuntimePanels(msg)"
              />
              <AgentAnswerContent
                :is-loading="!!msg.isLoading"
                :content-html="renderMessageContent(msg.content)"
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
            <textarea 
              ref="inputRef"
              v-model="inputValue"
              id="fastflow-input"
              placeholder="有问题，尽管问" 
              :rows="inputRows"
              @input="updateInputRows"
              @keydown="handleKeydown"
            ></textarea>
            
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
                  :disabled="!inputValue.trim() || isLoading"
                  @click="handleGenerate"
                >
                  <Send size="16" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="resize-handle nw" @pointerdown="resizer.startResize('nw', $event)"></div>
      <div class="resize-handle ne" @pointerdown="resizer.startResize('ne', $event)"></div>
      <div class="resize-handle sw" @pointerdown="resizer.startResize('sw', $event)"></div>
      <div class="resize-handle se" @pointerdown="resizer.startResize('se', $event)"></div>
    </div>
  </div>
</template>

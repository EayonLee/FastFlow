<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { useUserStore } from '@/stores/userStore'
import { streamChat } from '@/services/agentService'
import FlowSelect from '@/components/flow/controls/FlowSelect.vue'
import { getModelConfigs } from '@/services/modelConfigService'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { generateUUID } from '@/utils/uuid'

const { t } = useI18n()
const { showToast } = useToast()

const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>';
      } catch (__) {}
    }

    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>';
  }
})

const renderMarkdown = (content: string) => {
  if (!content) return ''
  
  // 处理模型可能返回的被 ```markdown 包裹的内容
  let processedContent = content.trim()
  
  // 检查是否被 markdown 代码块包裹
  if (processedContent.startsWith('```markdown') && processedContent.endsWith('```')) {
    processedContent = processedContent.slice(11, -3).trim()
  } else if (processedContent.startsWith('```') && processedContent.endsWith('```')) {
    // 检查是否是纯粹的代码块包裹（没有指定语言，或者其他语言）
    // 这里比较激进：如果整个内容就是一个代码块，我们假设用户其实想看里面的渲染内容
    // 除非它真的很像代码（比如有 import, function 等）
    // 但为了简单起见，我们先只处理 markdown 标记
    const firstLineBreak = processedContent.indexOf('\n')
    if (firstLineBreak > -1) {
       const firstLine = processedContent.slice(0, firstLineBreak).trim()
       if (firstLine === '```markdown' || firstLine === '```md') {
          processedContent = processedContent.slice(firstLineBreak + 1, -3).trim()
       }
    }
  }

  return md.render(processedContent)
}

const formatDate = (date: Date) => {
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

// 消息类型定义
interface Message {
  id: number
  role: 'ai' | 'user'
  content: string
  timestamp: string
  feedback?: 'like' | 'dislike' | null
  isError?: boolean
}

const messages = ref<Message[]>([
  { 
    id: 1, 
    role: 'ai', 
    content: 'Hi 我是 NEXUS，你的智能工作流助手。告诉我你想要什么样的工作流吧！', 
    timestamp: formatDate(new Date()),
    feedback: null,
    isError: false
  }
])

const userInput = ref('')
const isProcessing = ref(false)
const messagesContainer = ref<HTMLElement | null>(null)
// 当前会话ID，每次点击"新对话"时更新
const currentSessionId = ref('')

// 初始化会话ID
currentSessionId.value = generateUUID()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const copiedId = ref<number | null>(null)

const selectedModel = ref('')
const models = ref<{ label: string, value: string, id?: number }[]>([])

// 默认选择的智能体类型
const selectedAgentType = ref('chat')
// 智能体类型定义
const agentTypes = [
  { 
    label: 'SOLO Builder', 
    value: 'builder',
    icon: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="3" width="8" height="8" rx="2" stroke="#c084fc" stroke-width="2"/>
      <rect x="13" y="13" width="8" height="8" rx="2" stroke="#c084fc" stroke-width="2"/>
      <path d="M11 7H13V13H7V11" stroke="#c084fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="7" cy="7" r="1" fill="#c084fc"/>
      <circle cx="17" cy="17" r="1" fill="#c084fc"/>
    </svg>`
  },
  { 
    label: 'Chat', 
    value: 'chat', 
    icon: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M4 6C4 4.89543 4.89543 4 6 4H18C19.1046 4 20 4.89543 20 6V14C20 15.1046 19.1046 16 18 16H9L5 20V16H4C4 16 4 16 4 16V6Z" stroke="#22d3ee" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M8 10H16" stroke="#22d3ee" stroke-width="2" stroke-linecap="round" stroke-opacity="0.5"/>
      <circle cx="15" cy="6" r="2" fill="#22d3ee" stroke="#1a1a1a" stroke-width="2"/>
    </svg>`
  }
]

const fetchModels = async () => {
  try {
    // 获取模型配置列表
    const configs = await getModelConfigs()
    if (configs && configs.length > 0) {
      models.value = configs.map(config => ({
        label: config.modelName,
        value: config.modelName,
        id: config.id
      }))

      // 默认选中第一个
      if (!selectedModel.value && models.value.length > 0) {
        selectedModel.value = models.value[0]?.value || ''
      }
    } else {
       models.value = [
        { label: '暂无模型配置', value: '' }
      ]
      selectedModel.value = ''
    }
  } catch (error) {
    console.error('Failed to fetch models:', error)
    models.value = [
        { label: '暂无模型配置', value: '' }
      ]
      selectedModel.value = ''
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const startNewChat = () => {
  messages.value = [{ 
    id: Date.now(), 
    role: 'ai', 
    content: 'Hi 我是 NEXUS，你的智能工作流助手。告诉我你想要什么样的工作流吧！', 
    timestamp: formatDate(new Date()),
    feedback: null
  }]
  
  // 更新会话 ID
  currentSessionId.value = generateUUID()
  
  userInput.value = ''
  if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
    }
    showToast(t('common.new_chat_started'), 'success')
  }
  
  const showHistory = () => {
    showToast(t('common.history_feature_coming_soon'), 'info')
  }

const adjustHeight = () => {
  const textarea = textareaRef.value
  if (textarea) {
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 160) + 'px'
  }
}

const focusInput = () => {
  if (textareaRef.value) {
    textareaRef.value.focus()
  }
}

// 暴露给父组件调用
defineExpose({
  focusInput
})

// 获取当前用户名
const { userName } = useUserStore()

const copyToClipboard = async (msg: Message) => {
  try {
    await navigator.clipboard.writeText(msg.content)
    copiedId.value = msg.id
    setTimeout(() => {
      copiedId.value = null
    }, 2000)
  } catch (err) {
    console.error('Failed to copy', err)
  }
}

const handleFeedback = (msg: Message, type: 'like' | 'dislike') => {
  if (msg.feedback === type) {
    msg.feedback = null
  } else {
    msg.feedback = type
  }
}

const props = defineProps<{
  getGraphData?: () => Promise<{ nodes: any[], edges: any[] }>
}>()

const emit = defineEmits<{
  (e: 'update-graph', data: { type: 'layout' | 'graph', data: any }): void
}>()

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim() || isProcessing.value) return

  const now = new Date()
  const timestamp = formatDate(now)

  // 用户输入
  const content = userInput.value

  // 组装消息对象
  messages.value.push({
    id: Date.now(),
    role: 'user',
    content: content,
    timestamp
  })

  // 清空输入框
  userInput.value = ''
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }
  isProcessing.value = true
  scrollToBottom()

  // 发送后保持输入焦点
  await nextTick()
  focusInput()

  try {
    // 1. 创建 AI 回复占位
    const aiMsgId = Date.now() + 1
    const newAiMessage: Message = {
      id: aiMsgId,
      role: 'ai',
      content: '',
      timestamp: formatDate(new Date()),
      feedback: null,
      isError: false
    }
    messages.value.push(newAiMessage)
    // 获取响应式对象引用，确保更新触发 UI 渲染
    const aiMessage = messages.value.find(m => m.id === aiMsgId)!
    scrollToBottom()

    // 2. 获取当前图数据
    let currentGraph = null
    if (props.getGraphData) {
      try {
        const graphData = await props.getGraphData()
        currentGraph = {
          nodes: graphData.nodes.map(n => ({
            id: n.id,
            type: n.type,
            label: n.label || n.data?.label,
            config: n.data || {}
          })),
          edges: graphData.edges.map(e => ({
            source: e.source,
            target: e.target,
            source_handle: e.sourceHandle,
            target_handle: e.targetHandle
          }))
        }
      } catch (err) {
        console.error('Failed to get graph data:', err)
        // 继续执行，但不带图数据
      }
    }

    // 3. 查找选中的模型配置
    const selectedConfig = models.value.find(m => m.value === selectedModel.value)
    // 如果没有有效的模型配置（例如 "暂无模型配置"），则抛出错误
    if (!selectedModel.value) {
        throw new Error('当前没有可用的模型配置，请先在设置中添加模型。')
    }

    // 4. 准备请求体
    const context = {
      user_prompt: content,
      current_graph: currentGraph,
      model_config_id: selectedConfig ? selectedConfig.id : null,
      session_id: currentSessionId.value,
      agent_type: selectedAgentType.value
    }
    
    // 4. 发起流式请求
    await streamChat(context, {
      onChunk: (content: string) => {
        aiMessage.content += content
        scrollToBottom()
      },
      onGraphUpdate: (data: { type: 'layout' | 'graph', data: any }) => {
        emit('update-graph', data)
      },
      onError: (msg: string) => {
        aiMessage.content += `\n[Error: ${msg}]`
        aiMessage.isError = true
      }
    })

  } catch (error: any) {
    console.error('Chat error:', error)
    // 如果是最后一条消息是空的AI消息，则显示错误
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && lastMsg.role === 'ai') {
      if (!lastMsg.isError) {
        if (!lastMsg.content) {
          lastMsg.content = `Error: ${error.message || 'Connection failed'}`
        } else {
          lastMsg.content += `\n[Error: ${error.message || 'Connection failed'}]`
        }
        lastMsg.isError = true
      }
    }
  } finally {
    isProcessing.value = false
    scrollToBottom()
  }
}

onMounted(async () => {
  scrollToBottom()
  fetchModels()
  await nextTick()
  setTimeout(() => {
    focusInput()
  }, 100)
})
</script>

<template>
  <div class="ai-chat-panel">
    <!-- Background Grid (Moved to top level) -->
    <div class="grid-background"></div>

    <!-- Header -->
    <div class="chat-header">
      <div class="header-content">
        <div class="status-indicator">
          <div class="status-dot"></div>
          <span class="status-text"><span class="highlight">AI</span> ASSISTANT</span>
        </div>
        <div class="header-controls">
          <button class="chat-btn" @click="showHistory" :data-tooltip="t('common.history')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"></path>
            </svg>
          </button>
          <button class="chat-btn primary" @click="startNewChat" :data-tooltip="t('common.new_chat')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              <line x1="9" y1="10" x2="15" y2="10"></line>
              <line x1="12" y1="7" x2="12" y2="13"></line>
            </svg>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Messages Area -->
    <div class="messages-area" ref="messagesContainer">
      <!-- .grid-background removed from here -->
      
      <div 
        v-for="msg in messages" 
        :key="msg.id" 
        class="message-wrapper"
        :class="msg.role"
      >
        <div class="message-content-box">
          <div class="msg-header" v-if="msg.role === 'ai'">
            <span class="role-name">NEXUS</span>
            <span v-if="!msg.content && isProcessing" class="status-text-small">Thinking...</span>
            <span v-else class="msg-time">{{ msg.timestamp }}</span>
          </div>
          <div class="msg-header" v-else>
            <span class="role-name">{{ userName }}</span>
            <span class="msg-time">{{ msg.timestamp }}</span>
          </div>
          
          <div class="msg-body" :class="{ 'error-msg': msg.isError }">
             <div v-if="msg.role === 'ai'">
               <div v-if="!msg.content && isProcessing" class="processing-indicator">
                  <span class="dot"></span>
                  <span class="dot"></span>
                  <span class="dot"></span>
               </div>
               <div v-else class="markdown-content" v-html="renderMarkdown(msg.content)"></div>
             </div>
             <div v-else>{{ msg.content }}</div>
          </div>
          
          <div class="msg-actions" v-if="msg.role === 'ai' && !msg.isError && msg.content">
            <button 
              class="action-btn" 
              :class="{ active: copiedId === msg.id }"
              @click="copyToClipboard(msg)"
              :data-tooltip="t('common.copy')"
            >
              <svg v-if="copiedId === msg.id" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            </button>
            <div class="divider"></div>
            <button 
              class="action-btn" 
              :class="{ active: msg.feedback === 'like' }"
              @click="handleFeedback(msg, 'like')"
              :data-tooltip="t('common.like')"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
              </svg>
            </button>
            <button 
              class="action-btn" 
              :class="{ active: msg.feedback === 'dislike' }"
              @click="handleFeedback(msg, 'dislike')"
              :data-tooltip="t('common.dislike')"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
              </svg>
            </button>
          </div>
        </div>
      </div>


    </div>
    
    <!-- Input Area -->
    <div class="input-area">
      <div class="input-wrapper" @click="focusInput">
        <textarea 
            ref="textareaRef"
            v-model="userInput"
            :placeholder="t('editor.chat_placeholder')"
            @keydown.enter.exact.prevent="sendMessage"
            @input="adjustHeight"
            rows="3"
            autofocus
          ></textarea>
        
        <div class="input-footer">
          <div class="left-controls">
            <div class="agent-selector" @click.stop>
              <FlowSelect 
                v-model="selectedAgentType" 
                :options="agentTypes" 
                placeholder="Agent" 
                placement="top"
                borderless
              />
            </div>
          </div>

          <div class="right-controls">
            <div class="model-selector" @click.stop>
              <FlowSelect v-model="selectedModel" :options="models" placeholder="选择模型" />
            </div>

            <button class="send-btn" @click.stop="sendMessage" :disabled="!userInput || isProcessing">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface-color);
  border-left: 1px solid var(--border-color);
  color: var(--text-primary);
  position: relative;
  overflow: hidden;
}

/* Markdown Styles */
.markdown-content :deep(p) {
  margin-bottom: 0.5rem;
  line-height: 1.6;
}

.markdown-content :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(pre) {
  background: rgba(0, 0, 0, 0.2); /* 极低透明度，接近完全透明 */
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  padding: 12px;
  margin: 8px 0;
  overflow-x: auto;
  backdrop-filter: blur(4px); /* 添加磨砂玻璃效果 */
}

.markdown-content :deep(code) {
  font-family: 'Fira Code', monospace;
  font-size: 0.9em;
  background: rgba(120, 120, 120, 0.2);
  padding: 2px 4px;
  border-radius: 4px;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: #abb2bf;
}

/* Syntax Highlighting (One Dark inspired) */
.markdown-content :deep(.hljs-comment),
.markdown-content :deep(.hljs-quote) {
  color: #7f848e;
  font-style: italic;
}

.markdown-content :deep(.hljs-doctag),
.markdown-content :deep(.hljs-keyword),
.markdown-content :deep(.hljs-formula) {
  color: #c678dd;
}

.markdown-content :deep(.hljs-section),
.markdown-content :deep(.hljs-name),
.markdown-content :deep(.hljs-selector-tag),
.markdown-content :deep(.hljs-deletion),
.markdown-content :deep(.hljs-subst) {
  color: #e06c75;
}

.markdown-content :deep(.hljs-literal) {
  color: #56b6c2;
}

.markdown-content :deep(.hljs-string),
.markdown-content :deep(.hljs-regexp),
.markdown-content :deep(.hljs-addition),
.markdown-content :deep(.hljs-attribute),
.markdown-content :deep(.hljs-meta .hljs-string) {
  color: #98c379;
}

.markdown-content :deep(.hljs-attr),
.markdown-content :deep(.hljs-variable),
.markdown-content :deep(.hljs-template-variable),
.markdown-content :deep(.hljs-type),
.markdown-content :deep(.hljs-selector-class),
.markdown-content :deep(.hljs-selector-attr),
.markdown-content :deep(.hljs-selector-pseudo),
.markdown-content :deep(.hljs-number) {
  color: #d19a66;
}

.markdown-content :deep(.hljs-symbol),
.markdown-content :deep(.hljs-bullet),
.markdown-content :deep(.hljs-link),
.markdown-content :deep(.hljs-meta),
.markdown-content :deep(.hljs-selector-id),
.markdown-content :deep(.hljs-title) {
  color: #61aeee;
}

.markdown-content :deep(.hljs-built_in),
.markdown-content :deep(.hljs-title.class_),
.markdown-content :deep(.hljs-class .hljs-title) {
  color: #e6c07b;
}

.markdown-content :deep(ul), .markdown-content :deep(ol) {
  padding-left: 1.5rem;
  margin-bottom: 0.5rem;
}

.markdown-content :deep(li) {
  margin-bottom: 0.25rem;
}

.markdown-content :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid var(--border-color);
  margin: 0.5rem 0;
  padding-left: 1rem;
  color: var(--text-secondary);
}

.markdown-content :deep(h1), 
.markdown-content :deep(h2), 
.markdown-content :deep(h3), 
.markdown-content :deep(h4) {
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  font-weight: 600;
  line-height: 1.4;
}

.markdown-content :deep(h1) { font-size: 1.5em; }
.markdown-content :deep(h2) { font-size: 1.3em; }
.markdown-content :deep(h3) { font-size: 1.1em; }

.chat-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.02);
  position: relative;
  z-index: 10;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-controls {
  display: flex;
  gap: 8px;
}

.chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-dim);
  padding: 6px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  position: relative;
}

.chat-btn::after {
  content: attr(data-tooltip);
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  padding: 4px 8px;
  background: #1a1a1a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 10px;
  font-weight: 500;
  border-radius: 4px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  z-index: 100;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}

.chat-btn:hover::after {
  opacity: 1;
  visibility: visible;
}

.chat-btn:hover {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.05);
}

/* CSS Variables Replacement */
.chat-btn.primary {
  color: var(--accent-neon);
  border-color: transparent;
  background: transparent;
}

.chat-btn.primary:hover {
  background: rgba(0, 255, 65, 0.05);
  border-color: rgba(0, 255, 65, 0.2);
  box-shadow: 0 0 8px rgba(0, 255, 65, 0.15);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-dot {
  width: 6px;
  height: 6px;
  background: var(--accent-neon);
  border-radius: 50%;
  opacity: 0.8;
  box-shadow: 0 0 8px var(--accent-neon-dim);
}

.status-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  letter-spacing: 0.5px;
}

.status-text .highlight {
  color: var(--accent-neon);
}

/* Messages Area */
.messages-area {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.grid-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: 
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
  z-index: 0;
}

.message-wrapper {
  z-index: 1;
  display: flex;
  width: 100%;
  animation: slideIn 0.2s ease-out;
}

.message-wrapper.user {
  justify-content: flex-end;
}

.message-content-box {
  max-width: 88%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.msg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  opacity: 0.6;
  padding: 0 2px;
}

.message-wrapper.user .msg-header {
  flex-direction: row-reverse;
}

.role-name {
  font-weight: 600;
  color: var(--accent-neon);
  font-size: 12px;
}

.message-wrapper.user .role-name {
  color: #fff;
}

.msg-time {
  color: var(--text-dim);
  opacity: 0;
  transition: opacity 0.2s;
  font-size: 12px;
}

.message-wrapper:hover .msg-time {
  opacity: 1;
}

.msg-body {
  padding: 10px 14px;
  font-size: 13.5px;
  line-height: 1.5;
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  position: relative;
  transition: border-color 0.2s;
  /* white-space: pre-wrap; Removed for Markdown support */
  word-break: break-word;
}

.message-wrapper.ai .msg-body {
  border-top-left-radius: 2px;
}

.message-wrapper.ai .msg-body.error-msg {
  color: #ff4d4d;
  border-color: rgba(255, 77, 77, 0.5) !important;
  background: rgba(255, 77, 77, 0.1);
}

.message-wrapper.user .msg-body {
  border-top-right-radius: 2px;
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
}

.message-wrapper.ai:hover .msg-body {
  border-color: var(--accent-neon-dim);
}

.msg-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  padding-left: 2px;
  opacity: 0;
  transform: translateY(-2px);
  transition: all 0.2s ease;
}

.message-wrapper:hover .msg-actions {
  opacity: 1;
  transform: translateY(0);
}

.action-btn {
  background: transparent;
  border: none;
  color: var(--text-dim);
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  position: relative;
}

/* CSS Tooltip - No Delay */
.action-btn::after {
  content: attr(data-tooltip);
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  padding: 4px 8px;
  background: #1a1a1a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 10px;
  font-weight: 500;
  border-radius: 4px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  z-index: 100;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}

.action-btn:hover::after {
  opacity: 1;
  visibility: visible;
}

.action-btn:hover {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.05);
}

.action-btn.active {
  color: var(--accent-neon);
  background: rgba(0, 255, 65, 0.05);
}

.divider {
  width: 1px;
  height: 10px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 4px;
}

/* Processing Animation */
.status-text-small {
  color: var(--text-dim);
  font-style: italic;
}

.processing-indicator {
  display: flex;
  gap: 4px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  border-top-left-radius: 2px;
  width: fit-content;
}

.dot {
  width: 4px;
  height: 4px;
  background: var(--accent-neon);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

/* Input Area */
.input-area {
  padding: 16px 20px;
  background: #121212; /* 纯黑背景，遮挡网格 */
  border-top: 1px solid var(--border-color);
  position: relative;
  z-index: 5;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 8px 8px 8px 12px;
  transition: all 0.2s ease;
  box-shadow: 0 0 15px rgba(255, 255, 255, 0.05); /* 浅色光晕 */
}

.input-wrapper:focus-within {
  border-color: rgba(255, 255, 255, 0.2);
  box-shadow: 0 0 15px rgba(255, 255, 255, 0.1); /* 保持光晕风格一致，稍微亮一点点 */
}

textarea {
    width: 100%;
    background: transparent;
    border: none;
    color: #fff;
    font-family: inherit;
    font-size: 13px;
    outline: none;
    resize: none;
    line-height: 20px;
    padding: 4px 0;
    overflow-y: auto;
    min-height: 60px;
    box-sizing: border-box;
  }

textarea::placeholder {
  color: rgba(255, 255, 255, 0.2);
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding-top: 4px;
}

.left-controls {
  display: flex;
  align-items: center;
}

.right-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 模型和Agent选择器容器 */
.model-selector,
.agent-selector {
  position: relative;
  display: flex;
  align-items: center;
  width: auto; /* 取消固定宽度，自适应内容 */
  min-width: 0;
}

/* 覆盖 FlowSelect 容器宽度 */
.model-selector :deep(.flow-select-container),
.agent-selector :deep(.flow-select-container) {
  width: auto; /* 跟随内容宽度 */
  min-width: 0; /* 移除最小宽度限制，完全自适应 */
}

/* 触发器按钮样式 - 默认无背景无边框 */
.model-selector :deep(.flow-select-trigger),
.agent-selector :deep(.flow-select-trigger) {
  background: transparent; /* 默认透明 */
  border: none !important; /* 强制去除边框 */
  border-radius: 6px;
  padding: 6px 8px; /* 稍微减小内边距 */
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5); /* 默认字体颜色变暗 */
  transition: all 0.2s;
  box-shadow: none !important; /* 强制去除阴影 */
  gap: 6px; /* 文字和图标间距 */
}

.model-selector :deep(.flow-select-trigger) {
  justify-content: flex-end; /* 内容靠右对齐 */
}

.agent-selector :deep(.flow-select-trigger) {
  justify-content: flex-start; /* 内容靠左对齐 */
}

/* 触发器悬停状态 - 显示背景并高亮文字 */
.model-selector :deep(.flow-select-trigger:hover),
.agent-selector :deep(.flow-select-trigger:hover) {
  background: rgba(255, 255, 255, 0.05); /* 悬停时显示微弱背景 */
  border: none !important;
  color: var(--text-main); /* 悬停时字体变亮 */
}

/* 触发器展开状态 - 显示背景并高亮 */
.model-selector :deep(.flow-select-trigger.is-open),
.agent-selector :deep(.flow-select-trigger.is-open) {
  background: rgba(255, 255, 255, 0.05);
  box-shadow: none !important;
  color: var(--text-main); /* 展开时字体变亮 */
}

/* 选中文字样式 - 允许完整显示且紧凑 */
.model-selector :deep(.selected-text),
.agent-selector :deep(.selected-text) {
  text-overflow: unset;
  overflow: visible;
  flex: 0 1 auto; /* 取消自动撑满，保持紧凑 */
}

.model-selector :deep(.selected-text) {
  text-align: right; /* 文字右对齐 */
}

.agent-selector :deep(.selected-text) {
  text-align: left; /* 文字左对齐 */
}

/* 下拉选项菜单 - 向上展开 */
.model-selector :deep(.flow-select-options),
.agent-selector :deep(.flow-select-options) {
  top: auto; /* 清除顶部定位 */
  bottom: 100%; /* 向上定位 */
  margin-top: 0;
  margin-bottom: 8px; /* 底部间距 */
  background: rgba(10, 10, 12, 0.98);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 6px;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.45);
  min-width: 100%; /* 菜单宽度至少跟随触发器宽度 */
  width: max-content; /* 允许内容撑开宽度 */
}

.model-selector :deep(.flow-select-options) {
  left: auto; /* 清除左对齐 */
  right: 0; /* 改为右对齐 */
}

.agent-selector :deep(.flow-select-options) {
  left: 0; /* 左对齐 */
  right: auto;
}

/* 选项样式 */
.model-selector :deep(.flow-select-option),
.agent-selector :deep(.flow-select-option) {
  border-radius: 6px;
  padding: 8px 10px;
  color: var(--text-main);
  white-space: nowrap; /* 防止文字换行 */
}

/* 选项悬停样式 */
.model-selector :deep(.flow-select-option:hover),
.agent-selector :deep(.flow-select-option:hover) {
  background: rgba(0, 255, 65, 0.08);
  color: var(--accent-neon);
}

/* 选中选项样式 */
.model-selector :deep(.flow-select-option.is-selected),
.agent-selector :deep(.flow-select-option.is-selected) {
  background: rgba(0, 255, 65, 0.12);
  color: var(--accent-neon);
}

.send-btn {
  background: rgba(255, 255, 255, 0.05);
  border: none;
  color: var(--text-main);
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: var(--accent-neon);
  color: #000;
}

.send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Scrollbar */
.messages-area::-webkit-scrollbar {
  width: 4px;
}

.messages-area::-webkit-scrollbar-track {
  background: transparent;
}

.messages-area::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.messages-area::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { Bot, MessageSquare, Send, Copy, Check } from 'lucide-vue-next'
import FlowSelect from '@/components/FlowSelect.vue'
import Header from '@/components/Header.vue'
import { useCopyFeedback } from '@/composables/useCopyFeedback.js'
import { useResizable } from '@/composables/useResizable.js'
import { Bridge } from '@/services/bridge.js'
import { Nexus } from '@/services/nexus.js'
import { createAuthGuard } from '@/utils/authGuard.js'
import { getModelConfigs } from '@/services/modelConfig.js'
import { Layout } from '@/utils/layout.js'
import { generateUuid32 } from '@/utils/uuid.js'

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
    content: 'Hi 我是 NEXUS，你的智能工作流助手。告诉我你想要什么样的工作流吧！',
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
  storageKey: 'chat_box_size'
})

// 根据消息 ID 查找消息对象
function findMessage(id) {
  return messages.value.find(m => m.id === id)
}

// 写入错误消息并滚动到底部
function setMessageError(id, message) {
  const target = findMessage(id)
  if (!target) return
  target.isLoading = false
  target.content = message
  scrollToBottom()
}

// 将流式文本追加到指定消息
function appendChunkToMessage(id, chunk) {
  if (!chunk) return
  const target = findMessage(id)
  if (!target) return
  if (target.isLoading) {
    target.isLoading = false
  }
  target.content = `${target.content || ''}${chunk}`
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
})

onUnmounted(() => {
  // 清理登录态守卫与拖拽事件
  if (authGuard) {
    authGuard.stop()
    authGuard = null
  }
  resizer.cleanup()
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

// 添加消息辅助函数
function addMessage(content, type) {
  messages.value.push({
    id: generateUuid32(), // 使用 32 位 UUID，避免冲突
    type,
    content,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  })
  scrollToBottom()
}

// 复制消息内容到剪贴板
async function copyMessage(content, messageId) {
  await copyText(content, messageId)
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
  isLoading.value = true

  // 4) 显示加载中消息（用于流式更新）
  const loadingMsgId = generateUuid32() // 使用 32 位 UUID，避免冲突
  const loadingMsg = {
    id: loadingMsgId,
    type: 'ai',
    content: '',
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    isLoading: true
  }
  messages.value.push(loadingMsg)
  scrollToBottom()

  // 5) 获取当前工作流 JSON 配置
  let currentGraph = null
  try {
    currentGraph = await Bridge.getCurrentGraph()
  } catch (e) {
    setMessageError(loadingMsgId, `获取当前编排失败：\n${e.message}`)
    // 终止本次发送
    isLoading.value = false
    return
  }

  // 6) 调用 Nexus（SSE 流式）
  const isChatAgent = selectedAgent.value === 'chat'
  Nexus.generateWorkflow(
    {
      // 请求参数：prompt + 选中的 agent + 模型 + 会话 + 当前画布
      prompt,
      agentType: selectedAgent.value,
      modelConfigId: selectedModel.value,
      sessionId: sessionId.value,
      currentGraph
    },
    (chunk) => {
      // Chat/Builder 的流式文本统一追加到消息里
      appendChunkToMessage(loadingMsgId, chunk)
    },
    (graphData) => {
      // Chat 智能体不返回图，直接结束
      if (isChatAgent) {
        const targetMsg = findMessage(loadingMsgId)
        if (targetMsg?.isLoading) targetMsg.isLoading = false
        isLoading.value = false
        return
      }

      // Builder 成功回调 - 更新同一条消息
      const targetMsg = findMessage(loadingMsgId)
      if (targetMsg) {
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
      :class="{ active: isOpen, resizing: isResizing }"
      ref="containerRef"
    >
      <div class="chat-main-interface">
        <!-- 公共 Header -->
        <Header 
          show-close 
          @close="closeChat"
        />
        
        <!-- 消息区域 -->
        <div class="messages-area" ref="messagesContainer">
          <div 
            v-for="msg in messages" 
            :key="msg.id" 
            class="message-wrapper" 
            :class="msg.type"
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
                  <div class="msg-body">
                    <div v-if="msg.isLoading" class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                    <span v-else>{{ msg.content }}</span>
                  </div>
            </div>
          </div>
        </div>
        
        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-wrapper">
            <textarea 
              ref="inputRef"
              v-model="inputValue"
              id="fastflow-input"
              placeholder="有问题，尽管问" 
              rows="3"
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

<style scoped>
/* 
  Vue 视图组件样式
  这里主要保留对图标和布局的微调，大部分样式在 styles/components/chat.css 中定义
*/
.chat-view {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
/* 确保图标垂直居中 */
.lucide {
  vertical-align: middle;
}
</style>

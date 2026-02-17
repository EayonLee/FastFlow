<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  events: {
    type: Array,
    default: () => []
  },
  open: {
    type: Boolean,
    default: true
  },
  completed: {
    type: Boolean,
    default: false
  }
})

const localOpen = ref(true)

watch(
  () => props.open,
  (next) => {
    localOpen.value = !!next
  },
  { immediate: true }
)

const normalizedEvents = computed(() => {
  return props.events.map((event, index) => normalizeEvent(event, index))
})

const liveLine = computed(() => {
  const last = normalizedEvents.value.length ? normalizedEvents.value[normalizedEvents.value.length - 1] : null
  if (!last) return props.completed ? '执行完成' : 'Deep Thinking...'
  return last.detail
})

const liveLineKey = computed(() => {
  if (props.completed && !localOpen.value) return 'completed'
  const last = normalizedEvents.value.length ? normalizedEvents.value[normalizedEvents.value.length - 1] : null
  return String(last?.id || `${normalizedEvents.value.length}-${liveLine.value}`)
})

function normalizeEvent(event, index) {
  const eventType = String(event?.type || '').trim()
  const phase = String(event?.phase || '').trim()
  const detailFromMessage = String(event?.message || '').trim()
  const toolName = String(event?.toolName || '').trim()

  if (eventType === 'run.started') {
    return buildNormalizedEvent(event, index, '会话状态', detailFromMessage || '开始处理用户问题')
  }
  if (eventType === 'run.completed') {
    return buildNormalizedEvent(event, index, '会话状态', detailFromMessage || '本轮处理完成')
  }

  if (eventType === 'phase.started' || eventType === 'phase.completed') {
    return buildPhaseEvent(event, index, phase, eventType === 'phase.completed', detailFromMessage)
  }

  if (eventType === 'tool.selected') {
    return buildNormalizedEvent(event, index, '工具执行', detailFromMessage || `模型选择工具：${toolName}`)
  }
  if (eventType === 'tool.started') {
    return buildNormalizedEvent(event, index, '工具执行', detailFromMessage || `开始执行工具：${toolName}`)
  }
  if (eventType === 'tool.completed') {
    return buildNormalizedEvent(event, index, '工具执行', detailFromMessage || `工具执行完成：${toolName}`)
  }
  if (eventType === 'tool.failed') {
    return buildNormalizedEvent(event, index, '工具执行', detailFromMessage || `工具执行失败：${toolName}`)
  }

  if (eventType === 'review.started') {
    return buildNormalizedEvent(event, index, '模型回答效果审查', detailFromMessage || '正在审查模型回答是否满足用户问题')
  }
  if (eventType === 'answer.reset') {
    return buildNormalizedEvent(event, index, '模型回答效果审查', detailFromMessage || '候选回答未通过审查，继续补充信息')
  }

  return buildNormalizedEvent(event, index, '执行事件', detailFromMessage || eventType || '处理中')
}

function buildPhaseEvent(event, index, phase, completed, detailFromMessage) {
  const title = getPhaseTitle(phase)
  const fallbackDetail = getPhaseDetail(phase, completed)
  const detail = sanitizePhaseMessage(detailFromMessage) || fallbackDetail
  return buildNormalizedEvent(event, index, title, detail)
}

function getPhaseTitle(phase) {
  if (phase === 'analyze_question') return '问题理解'
  if (phase === 'execute_tools') return '工具执行'
  if (phase === 'review_answer') return '模型回答效果审查'
  if (phase === 'generate_final_answer') return '回答生成'
  return '执行阶段'
}

function getPhaseDetail(phase, completed) {
  if (phase === 'analyze_question') return completed ? '完成理解用户问题' : '开始理解用户问题'
  if (phase === 'execute_tools') return completed ? '完成工具执行流程' : '开始执行工具调用'
  if (phase === 'review_answer') return completed ? '完成模型回答充足性审查' : '开始审查模型回答充足性'
  if (phase === 'generate_final_answer') return completed ? '完成最终回答生成' : '开始生成最终回答'
  return completed ? '阶段已完成' : '阶段开始'
}

function sanitizePhaseMessage(message) {
  if (!message) return ''
  if (message.startsWith('阶段完成：')) return ''
  return message
}

function buildNormalizedEvent(event, index, title, detail) {
  return {
    id: String(event?.id || `${index}-${event?.type || 'event'}`),
    type: String(event?.type || ''),
    title: String(title || '').trim(),
    detail: String(detail || '').trim(),
    elapsedMs: Number.isFinite(event?.elapsedMs) ? event.elapsedMs : null,
    result: String(event?.result || '')
  }
}

function getToneClass(type) {
  if (type === 'tool.failed') return 'is-danger'
  if (type === 'tool.completed' || type === 'phase.completed' || type === 'run.completed') return 'is-success'
  if (type === 'tool.started' || type === 'phase.started' || type === 'review.started') return 'is-running'
  return 'is-neutral'
}

function canExpandResult(event) {
  return !!String(event?.result || '').trim()
}

function handleToggle(event) {
  localOpen.value = !!event?.target?.open
}
</script>

<template>
  <details
    class="runtime-panel"
    :class="{ 'is-completed': completed }"
    :open="localOpen"
    @toggle="handleToggle"
  >
    <summary class="runtime-summary">
      <span class="runtime-title">执行过程</span>
      <div class="runtime-collapsed-line">
        <span v-if="!localOpen && completed" class="runtime-collapsed-hint">点击展开查看完整内容</span>
        <span v-else-if="localOpen" class="runtime-collapsed-empty"></span>
        <transition v-else name="runtime-line-slide" mode="out-in">
          <span :key="liveLineKey" class="runtime-collapsed-text">{{ liveLine }}</span>
        </transition>
      </div>
    </summary>

    <ol class="runtime-list">
      <li v-if="!normalizedEvents.length" class="runtime-empty">Deep Thinking...</li>
      <li v-for="event in normalizedEvents" :key="event.id" class="runtime-item">
        <span class="runtime-dot" :class="getToneClass(event.type)"></span>
        <div class="runtime-main">
          <div class="runtime-row">
            <span class="runtime-type">{{ event.title }}</span>
            <span v-if="event.elapsedMs !== null && event.elapsedMs !== undefined" class="runtime-elapsed">
              {{ event.elapsedMs }}ms
            </span>
          </div>
          <p class="runtime-text">{{ event.detail || '处理中' }}</p>

          <details v-if="canExpandResult(event)" class="runtime-result">
            <summary>查看工具结果</summary>
            <pre>{{ event.result }}</pre>
          </details>
        </div>
      </li>
    </ol>
  </details>
</template>

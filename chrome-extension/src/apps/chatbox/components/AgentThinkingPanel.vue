<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  open: {
    type: Boolean,
    default: true
  },
  completed: {
    type: Boolean,
    default: false
  },
  runtimeStatus: {
    type: String,
    default: 'running'
  },
  placeholder: {
    type: Boolean,
    default: false
  }
})

const localOpen = ref(true)
const EMPTY_THINKING_HINT = '本轮未返回思考内容'
const EMPTY_THINKING_DETAIL = '本轮未返回思考内容。'
const CANCELLED_THINKING_HINT = '思考已停止：本轮生成已手动停止'
const CANCELLED_THINKING_DETAIL = '思考已停止：你已手动终止本轮生成。'
const FAILED_THINKING_HINT = '思考中断：请求失败'
const FAILED_THINKING_DETAIL = '思考中断：本次请求失败，请重试或检查模型配置/网络。'
const dotStep = ref(1)
let dotTimer = null
const isCancelled = computed(() => props.runtimeStatus === 'cancelled')
const isFailed = computed(() => props.runtimeStatus === 'failed')
const animatedThinkingText = computed(() => `Deep Thinking ${'.'.repeat(dotStep.value)}`)
const hasContent = computed(() => !!String(props.content || '').trim())
const shouldRender = computed(() => props.placeholder || hasContent.value)
const collapsedEmptyHint = computed(() => {
  if (isCancelled.value) return CANCELLED_THINKING_HINT
  if (isFailed.value) return FAILED_THINKING_HINT
  return EMPTY_THINKING_HINT
})
const liveLine = computed(() => {
  const merged = String(props.content || '').replace(/\s+/g, ' ').trim()
  if (!merged) {
    if (isCancelled.value) return CANCELLED_THINKING_HINT
    if (isFailed.value) return FAILED_THINKING_HINT
    return props.completed ? EMPTY_THINKING_HINT : animatedThinkingText.value
  }

  const segments = merged
    .split(/[。！？!?；;\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
  const latest = segments.length ? segments[segments.length - 1] : merged
  if (latest.length <= 72) return latest
  return latest.slice(-72)
})
const fullThinkingText = computed(() => {
  if (hasContent.value) return props.content
  if (isCancelled.value) return CANCELLED_THINKING_DETAIL
  if (isFailed.value) return FAILED_THINKING_DETAIL
  return props.completed ? EMPTY_THINKING_DETAIL : animatedThinkingText.value
})
watch(
  () => props.open,
  (next) => {
    localOpen.value = !!next
  },
  { immediate: true }
)

function handleToggle(event) {
  localOpen.value = !!event?.target?.open
}

watch(
  () => [isCancelled.value, isFailed.value, props.completed],
  ([cancelled, failed, completed]) => {
    if (cancelled || failed || completed) {
      if (dotTimer) {
        clearInterval(dotTimer)
        dotTimer = null
      }
      return
    }
    if (!dotTimer) {
      dotTimer = setInterval(() => {
        dotStep.value = dotStep.value >= 3 ? 1 : dotStep.value + 1
      }, 420)
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (dotTimer) {
    clearInterval(dotTimer)
    dotTimer = null
  }
})
</script>

<template>
  <details
    v-if="shouldRender"
    class="thinking-panel"
    :class="{ 'is-completed': completed }"
    :open="localOpen"
    @toggle="handleToggle"
  >
    <summary class="thinking-summary">
      <span class="thinking-title">思考过程</span>
      <div class="thinking-collapsed-line">
        <span v-if="!localOpen && completed && hasContent" class="thinking-collapsed-hint">点击展开查看完整内容</span>
        <span v-else-if="!localOpen && completed && !hasContent" class="thinking-collapsed-hint">
          {{ collapsedEmptyHint }}
        </span>
        <span v-else-if="localOpen" class="thinking-collapsed-empty"></span>
        <span v-else class="thinking-collapsed-text">{{ liveLine }}</span>
      </div>
    </summary>
    <div class="thinking-body">
      <pre class="thinking-content">{{ fullThinkingText }}</pre>
    </div>
  </details>
</template>

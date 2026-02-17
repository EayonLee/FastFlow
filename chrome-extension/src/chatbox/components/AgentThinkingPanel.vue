<script setup>
import { computed, ref, watch } from 'vue'

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
  placeholder: {
    type: Boolean,
    default: false
  }
})

const localOpen = ref(true)
const hasContent = computed(() => !!String(props.content || '').trim())
const shouldRender = computed(() => props.placeholder || hasContent.value)
const liveLine = computed(() => {
  const merged = String(props.content || '').replace(/\s+/g, ' ').trim()
  if (!merged) return props.completed ? '思考完成' : 'Deep Thinking...'

  const segments = merged
    .split(/[。！？!?；;\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
  const latest = segments.length ? segments[segments.length - 1] : merged
  if (latest.length <= 72) return latest
  return latest.slice(-72)
})
const liveLineKey = computed(() => {
  if (props.completed) return 'completed'
  const merged = String(props.content || '').replace(/\s+/g, ' ').trim()
  if (!merged) return '0'
  const sentenceCount = merged
    .split(/[。！？!?；;\n]/)
    .map((item) => item.trim())
    .filter(Boolean).length
  const lengthBucket = Math.floor(merged.length / 24)
  return `${sentenceCount}-${lengthBucket}`
})
const fullThinkingText = computed(() => {
  if (hasContent.value) return props.content
  return props.completed ? '异常：本轮未收到思考内容，请检查模型是否开启思考输出。' : 'Deep Thinking...'
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
        <span v-if="!localOpen && completed" class="thinking-collapsed-hint">点击展开查看完整内容</span>
        <span v-else-if="localOpen" class="thinking-collapsed-empty"></span>
        <transition v-else name="thinking-line-slide" mode="out-in">
          <span :key="liveLineKey" class="thinking-collapsed-text">{{ liveLine }}</span>
        </transition>
      </div>
    </summary>
    <div class="thinking-body">
      <pre class="thinking-content">{{ fullThinkingText }}</pre>
    </div>
  </details>
</template>

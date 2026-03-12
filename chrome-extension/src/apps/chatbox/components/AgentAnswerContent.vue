<script setup>
import { Check, Copy } from 'lucide-vue-next'

defineEmits(['copy'])

defineProps({
  isLoading: {
    type: Boolean,
    default: false
  },
  contentHtml: {
    type: String,
    default: ''
  },
  showCopy: {
    type: Boolean,
    default: false
  },
  copied: {
    type: Boolean,
    default: false
  }
})
</script>

<template>
  <div class="msg-body">
    <div v-if="isLoading" class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
    <div v-else class="msg-markdown" v-html="contentHtml"></div>
    <button
      v-if="showCopy"
      class="copy-btn copy-btn-bubble"
      title="复制内容"
      @click="$emit('copy')"
    >
      <Check v-if="copied" size="12" />
      <Copy v-else size="12" />
    </button>
  </div>
</template>

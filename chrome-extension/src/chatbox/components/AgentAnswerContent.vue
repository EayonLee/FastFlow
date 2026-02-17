<script setup>
defineProps({
  isLoading: {
    type: Boolean,
    default: false
  },
  contentHtml: {
    type: String,
    default: ''
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
  </div>
</template>

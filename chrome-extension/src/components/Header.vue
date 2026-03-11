<script setup>
/**
 * 公共 Header 组件
 * 作用：统一 Popup 和 Chat 界面的头部样式
 */
import { X } from 'lucide-vue-next'
import { computed } from 'vue'
import { EXTENSION_VERSION_NAME } from '@config'

const props = defineProps({
  showClose: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: 'FastFlow Copilot'
  },
})

const version = computed(() => {
  return `v${EXTENSION_VERSION_NAME}`
})

const emit = defineEmits(['close', 'title-click'])
</script>

<template>
  <div class="common-header">
    <div class="header-content">
      <div class="status-indicator" @click="$emit('title-click')">
        <div class="status-dot"></div>
        <span class="status-text">
          Fast<span class="highlight neon-flicker">Flow</span> Copilot 
          <span class="version-tag">{{ version }}</span>
        </span>
      </div>
      
      <div class="header-controls" v-if="showClose">
        <button class="icon-btn close-btn" @click="$emit('close')" title="关闭窗口">
          <X size="14" />
        </button>
      </div>
    </div>
  </div>
</template>

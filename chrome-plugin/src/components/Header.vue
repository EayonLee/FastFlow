<script setup>
/**
 * 公共 Header 组件
 * 作用：统一 Popup 和 Chat 界面的头部样式
 */
import { X } from 'lucide-vue-next'
import { computed } from 'vue'

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

// 从 manifest 获取版本号
const version = computed(() => {
  try {
    return `v${chrome.runtime.getManifest().version}`
  } catch (e) {
    return 'Dev'
  }
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

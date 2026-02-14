<script setup>
/**
 * Neon Button Component
 * 封装了霓虹风格按钮的样式和交互逻辑
 */
defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  large: {
    type: Boolean,
    default: false
  },
  fullWidth: {
    type: Boolean,
    default: false
  }
})

defineEmits(['click'])
</script>

<template>
  <button 
    class="neon-btn" 
    :class="{ 'large': large, 'full-width': fullWidth }"
    :disabled="disabled"
    @click="$emit('click')"
  >
    <slot></slot>
  </button>
</template>

<style scoped>
.neon-btn {
  /* 基础样式 */
  background-color: transparent !important;
  border: 1px solid var(--accent-neon) !important;
  /* 亮色主题下也需要可读：默认使用主文本色 */
  color: var(--text-primary) !important;
  border-radius: 8px;
  cursor: pointer;
  font-family: var(--font-ui);
  font-weight: 600;
  transition: all 0.2s ease;
  box-shadow: 0 0 10px color-mix(in srgb, var(--accent-neon) 18%, transparent);
  position: relative;
  overflow: hidden;
  
  /* 默认尺寸 */
  padding: 8px 16px;
  font-size: 14px;
}

/* 尺寸变体 */
.neon-btn.large {
  padding: 12px 24px;
  font-size: 16px;
  min-width: 160px;
}

.neon-btn.full-width {
  width: 100%;
}

/* Hover 状态 - 确保高优先级 */
.neon-btn:hover:not(:disabled) {
  background-color: var(--accent-neon) !important;
  color: #050505 !important;
  box-shadow: 0 0 20px color-mix(in srgb, var(--accent-neon) 55%, transparent);
  transform: translateY(-1px);
}

/* Fallback for when CSS variables are missing */
@supports not (border-color: var(--accent-neon)) {
  .neon-btn {
    border-color: #00ff41 !important;
  }
  .neon-btn:hover:not(:disabled) {
    background-color: #00ff41 !important;
  }
}

/* Active 状态 */
.neon-btn:active:not(:disabled) {
  transform: translateY(1px);
}

/* Disabled 状态 */
.neon-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  border-color: var(--border-subtle) !important;
  color: var(--text-dim) !important;
  box-shadow: none;
}
</style>

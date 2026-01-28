<script setup lang="ts">
import { computed } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { json } from '@codemirror/lang-json'
import { oneDark } from '@codemirror/theme-one-dark'

const props = defineProps<{
  modelValue: string
  height?: string
  readOnly?: boolean
}>()

const emit = defineEmits(['update:modelValue', 'change'])

const extensions = [json(), oneDark]

const style = computed(() => ({
  height: '100%',
  backgroundColor: 'transparent', // Match theme
  fontSize: '13px'
}))

const wrapperStyle = computed(() => ({
  height: props.height || '500px'
}))

const handleChange = (val: string) => {
  emit('update:modelValue', val)
  emit('change', val)
}
</script>

<template>
  <div class="code-editor-wrapper" :style="wrapperStyle">
    <Codemirror
      :model-value="modelValue"
      :style="style"
      :extensions="extensions"
      :disabled="readOnly"
      :autofocus="true"
      :indent-with-tab="true"
      :tab-size="2"
      placeholder="Please enter JSON content..."
      @update:model-value="handleChange"
    />
  </div>
</template>

<style scoped>
.code-editor-wrapper {
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.2); /* Subtle dark background */
}

:deep(.cm-editor) {
  height: 100%;
  background-color: transparent !important;
}

:deep(.cm-scroller) {
  font-family: 'Fira Code', 'Consolas', monospace;
  line-height: 1.5;
}

:deep(.cm-gutters) {
  background-color: transparent !important;
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  color: #666;
}

:deep(.cm-activeLineGutter) {
  background-color: rgba(255, 255, 255, 0.05) !important;
}

:deep(.cm-activeLine) {
  background-color: rgba(255, 255, 255, 0.05) !important;
}
</style>

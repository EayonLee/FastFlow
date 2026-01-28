<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  modelValue: string | number | undefined
  placeholder?: string
  disabled?: boolean
  label?: string
  rows?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}>()

const { t } = useI18n()
const isModalOpen = ref(false)
const localValue = ref('')

// 在打开模态框时同步modelValue到localValue
const openModal = () => {
  if (props.disabled) return
  localValue.value = String(props.modelValue || '')
  isModalOpen.value = true
  nextTick(() => {

  })
}

const closeModal = () => {
  isModalOpen.value = false
}

const confirmChange = () => {
  emit('update:modelValue', localValue.value)
  emit('change', localValue.value)
  closeModal()
}

const handleInlineInput = (e: Event) => {
  const val = (e.target as HTMLTextAreaElement).value
  emit('update:modelValue', val)
}

</script>

<template>
  <div class="flow-textarea-container">
    <div class="textarea-wrapper">
      <textarea
        class="flow-textarea-input nodrag"
        :value="modelValue"
        :placeholder="placeholder"
        :rows="rows || 3"
        :disabled="disabled"
        @input="handleInlineInput"
      ></textarea>
      
      <button 
        class="maximize-btn" 
        @click="openModal" 
        :disabled="disabled"
        title="Expand Editor"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 3 21 3 21 9"></polyline>
          <polyline points="9 21 3 21 3 15"></polyline>
          <line x1="21" y1="3" x2="14" y2="10"></line>
          <line x1="3" y1="21" x2="10" y2="14"></line>
        </svg>
      </button>
    </div>

    <!-- Modal -->
    <Teleport to="body">
      <div v-if="isModalOpen" class="flow-modal-overlay" @click.self="closeModal">
        <div class="flow-modal-content">
          <div class="flow-modal-header">
            <h3>{{ label || 'Edit Content' }}</h3>
            <button class="close-btn" @click="closeModal">×</button>
          </div>
          
          <div class="flow-modal-body">
            <textarea
              v-model="localValue"
              class="large-editor"
              :placeholder="placeholder"
            ></textarea>
          </div>
          
          <div class="flow-modal-footer">
            <button class="btn-ghost" @click="closeModal">{{ t('common.cancel') }}</button>
            <button class="btn-neon" @click="confirmChange">{{ t('common.confirm') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.flow-textarea-container {
  width: 100%;
  position: relative;
}

.textarea-wrapper {
  position: relative;
  width: 100%;
}

.flow-textarea-input {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 8px 30px 8px 8px; /* Right padding for button */
  font-size: 12px;
  color: #ddd;
  width: 100%;
  box-sizing: border-box;
  outline: none;
  transition: border-color 0.2s;
  resize: none; /* Disable resize as requested */
  min-height: 60px;
  font-family: inherit;
  line-height: 1.5;
  display: block;
}

.flow-textarea-input:focus {
  border-color: var(--accent-neon, #00ff41);
  background: rgba(0, 0, 0, 0.4);
}

.flow-textarea-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.maximize-btn {
  position: absolute;
  bottom: 6px;
  right: 6px;
  background: transparent;
  border: none;
  color: #888;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0.6;
}

.maximize-btn:hover:not(:disabled) {
  background: transparent;
  color: var(--accent-neon, #00ff41);
  opacity: 1;
}

.maximize-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Modal Styles */
.flow-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  backdrop-filter: blur(5px);
}

.flow-modal-content {
  background: #1e1e1e;
  border: 1px solid #333;
  border-radius: 12px;
  width: 600px;
  max-width: 90vw;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
}

.flow-modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.flow-modal-header h3 {
  margin: 0;
  font-size: 16px;
  color: #fff;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.close-btn:hover {
  color: #fff;
}

.flow-modal-body {
  padding: 20px;
  flex: 1;
}

.large-editor {
  width: 100%;
  height: 400px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 16px;
  font-size: 14px;
  color: #ddd;
  box-sizing: border-box;
  outline: none;
  resize: none;
  font-family: var(--font-mono, monospace);
  line-height: 1.6;
}

.large-editor:focus {
  border-color: var(--accent-neon, #00ff41);
}

.flow-modal-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* Button Styles from global or scoped */
.btn-ghost {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #ccc;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
}

.btn-ghost:hover {
  border-color: #fff;
  color: #fff;
}

.btn-neon {
  background: rgba(0, 255, 65, 0.1);
  border: 1px solid var(--accent-neon, #00ff41);
  color: var(--accent-neon, #00ff41);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
  font-weight: 600;
}

.btn-neon:hover {
  background: var(--accent-neon, #00ff41);
  color: #000;
  box-shadow: 0 0 10px rgba(0, 255, 65, 0.3);
}
</style>

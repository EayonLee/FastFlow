<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

interface Option {
  label: string
  value: string | number
  icon?: string
}

const props = withDefaults(defineProps<{
  modelValue: string | number | undefined
  options: (string | number | Option)[]
  placeholder?: string
  disabled?: boolean
  placement?: 'top' | 'bottom'
  borderless?: boolean
}>(), {
  placement: 'bottom',
  borderless: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void
  (e: 'change', value: string | number): void
}>()

const isOpen = ref(false)
const containerRef = ref<HTMLElement | null>(null)

const normalizedOptions = computed(() => {
  return props.options.map(opt => {
    if (typeof opt === 'object' && opt !== null && 'value' in opt) {
      return opt as Option
    }
    return { label: String(opt), value: opt as string | number }
  })
})

const selectedOption = computed(() => {
  return normalizedOptions.value.find(opt => opt.value === props.modelValue)
})

const selectedLabel = computed(() => {
  return selectedOption.value ? selectedOption.value.label : ''
})

const toggleDropdown = () => {
  if (props.disabled) return
  isOpen.value = !isOpen.value
}

const selectOption = (option: Option) => {
  emit('update:modelValue', option.value)
  emit('change', option.value)
  isOpen.value = false
}

const closeDropdown = (e: MouseEvent) => {
  if (containerRef.value && !containerRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeDropdown)
})

onUnmounted(() => {
  document.removeEventListener('click', closeDropdown)
})
</script>

<template>
  <div class="flow-select-container" ref="containerRef">
    <div 
      class="flow-select-trigger" 
      :class="{ 
        'is-open': isOpen, 
        'is-disabled': disabled,
        'is-borderless': borderless
      }"
      @click="toggleDropdown"
    >
      <div class="trigger-content">
        <span v-if="selectedOption?.icon" class="option-icon" v-html="selectedOption.icon"></span>
        <span class="selected-text" :class="{ 'is-placeholder': !selectedLabel }">
          {{ selectedLabel || placeholder || 'Select...' }}
        </span>
      </div>
      <span class="arrow-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </span>
    </div>
    
    <div v-if="isOpen" class="flow-select-options" :class="`placement-${placement}`">
      <div 
        v-for="option in normalizedOptions" 
        :key="String(option.value)"
        class="flow-select-option"
        :class="{ 'is-selected': option.value === modelValue }"
        @click="selectOption(option)"
      >
        <span v-if="option.icon" class="option-icon" v-html="option.icon"></span>
        {{ option.label }}
      </div>
      <div v-if="normalizedOptions.length === 0" class="flow-select-empty">
        No options
      </div>
    </div>
  </div>
</template>

<style scoped>
.flow-select-container {
  position: relative;
  width: 100%;
}

.flow-select-trigger {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 6px 8px;
  font-size: 12px;
  color: #ddd;
  width: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: all 0.2s;
  height: 32px; /* Match input height */
}

.flow-select-trigger.is-borderless {
  background: transparent;
  border-color: transparent;
  padding-left: 4px; /* Slightly less padding to align better */
}

.flow-select-trigger:hover:not(.is-disabled) {
  border-color: rgba(255, 255, 255, 0.3);
}

.flow-select-trigger.is-borderless:hover:not(.is-disabled) {
  background: rgba(255, 255, 255, 0.05);
  border-color: transparent;
}

.flow-select-trigger.is-open {
  border-color: var(--accent-neon, #00ff41);
  background: rgba(0, 0, 0, 0.4);
}

.flow-select-trigger.is-borderless.is-open {
  background: rgba(255, 255, 255, 0.05);
  border-color: transparent;
}

.flow-select-trigger.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: rgba(0, 0, 0, 0.1);
}

.trigger-content {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  flex: 1;
}

.selected-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.selected-text.is-placeholder {
  color: #888;
}

.arrow-icon {
  display: flex;
  align-items: center;
  color: #888;
  transition: transform 0.2s;
}

.flow-select-trigger.is-open .arrow-icon {
  transform: rotate(180deg);
  color: var(--accent-neon, #00ff41);
}

.option-icon {
  display: flex;
  align-items: center;
  color: inherit;
  width: 16px;
  height: 16px;
}

.option-icon :deep(svg) {
  width: 100%;
  height: 100%;
}

.flow-select-options {
  position: absolute;
  left: 0;
  width: 100%;
  background: #1e1e1e;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  z-index: 100;
  max-height: 200px;
  overflow-y: auto;
  padding: 4px 0;
}

.flow-select-options.placement-bottom {
  top: 100%;
  margin-top: 4px;
}

.flow-select-options.placement-top {
  bottom: 100%;
  margin-bottom: 4px;
}

.flow-select-option {
  padding: 8px 12px;
  font-size: 12px;
  color: #ddd;
  cursor: pointer;
  transition: all 0.1s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.flow-select-option:hover {
  background: rgba(0, 255, 65, 0.1);
  color: var(--accent-neon, #00ff41);
}

.flow-select-option.is-selected {
  background: rgba(0, 255, 65, 0.15);
  color: var(--accent-neon, #00ff41);
  font-weight: 600;
}

.flow-select-empty {
  padding: 8px 12px;
  font-size: 12px;
  color: #666;
  text-align: center;
}

/* Scrollbar styling for options */
.flow-select-options::-webkit-scrollbar {
  width: 6px;
}

.flow-select-options::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

.flow-select-options::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.flow-select-options::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>

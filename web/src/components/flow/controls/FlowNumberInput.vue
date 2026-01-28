<script setup lang="ts">
const props = defineProps<{
  modelValue: number | undefined
  min?: number | null
  max?: number | null
  step?: number | null
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
  (e: 'change', value: number): void
}>()

const handleInput = (e: Event) => {
  const target = e.target as HTMLInputElement
  let val = parseFloat(target.value)

  // Handle empty input or NaN - treat as 0 or min?
  // If user clears input, we might want to allow it temporarily or reset to min
  // For now, if NaN, we ignore or set to 0 if min allows 0
  if (isNaN(val)) {
     // If empty, let it be empty in UI but don't emit valid number?
     // Or emit 0?
     // Let's emit 0 for now as most number inputs in this app (like history) default to 0
     val = 0
  }

  // Strict Validation logic
  if (props.min !== null && props.min !== undefined && val < props.min) {
    val = props.min
  }
  if (props.max !== null && props.max !== undefined && val > props.max) {
    val = props.max
  }

  // Update DOM if we clamped it
  // This ensures the user sees the clamped value immediately
  if (parseFloat(target.value) !== val) {
    target.value = val.toString()
  }

  emit('update:modelValue', val)
  emit('change', val)
}
</script>

<template>
  <input
    type="number"
    class="flow-node-input-field nodrag number-input"
    :value="modelValue"
    :min="min ?? undefined"
    :max="max ?? undefined"
    :step="step ?? undefined"
    :placeholder="placeholder"
    :disabled="disabled"
    @input="handleInput"
  />
</template>

<style scoped>
@import '@/components/flow/styles/NodeBase.css';

.number-input {
  height: 32px;
  min-height: 32px !important;
  padding: 0 8px;
}
</style>

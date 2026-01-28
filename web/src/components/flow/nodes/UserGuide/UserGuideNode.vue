<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import FlowTextarea from '@/components/flow/controls/FlowTextarea.vue'
import type { NodeInput, NodeOutput } from '@/services/workflowService'

interface NodeData {
  name: string
  intro?: string
  icon?: string
  inputs: NodeInput[]
  outputs: NodeOutput[]
  [key: string]: any
}

const props = defineProps<{
  id: string
  data: NodeData
  selected?: boolean
}>()

const { t } = useI18n()

const nodeName = computed(() => {
  return props.data?.name
})

const intro = computed(() => {
  return props.data?.intro || ''
})
</script>

<template>
  <div class="flow-node-card" :class="{ selected }">
    <div class="flow-node-icon-container">
      <span class="flow-node-icon">{{ data.icon || '⚙️' }}</span>
    </div>
    <div class="flow-node-title">{{ nodeName }}</div>
    <div class="flow-node-desc" v-if="intro" :title="intro">{{ intro }}</div>

    <!-- Dynamic Inputs -->
    <div class="flow-node-inputs" v-if="data.inputs && data.inputs.length">
      <div class="flow-node-inputs-header">{{ t('editor.inputs') }}</div>
      <div 
        v-for="input in data.inputs" 
        :key="input.key" 
        class="flow-node-input-item"
      >
        <div class="flow-node-input-label">
          {{ input.label }} <span v-if="input.required" style="color: #ff4d4f">*</span>
        </div>
        
        <!-- Textarea Renderer -->
        <FlowTextarea
          v-if="input.renderTypeList?.includes('textarea')"
          v-model="input.value"
          :placeholder="input.placeholder || input.description || ''"
          :label="input.label"
        />
        
        <!-- Default Text Input -->
        <input
          v-else
          type="text"
          class="flow-node-input-field nodrag"
          style="min-height: 32px;"
          :placeholder="input.placeholder || input.description || ''"
          :value="input.value"
          @input="(e) => input.value = (e.target as HTMLInputElement).value"
        />
      </div>
    </div>

    <!-- Dynamic Outputs -->
    <div class="flow-node-outputs" v-if="data.outputs && data.outputs.length">
      <div class="flow-node-outputs-header">{{ t('editor.outputs') }}</div>
      <div 
        v-for="output in data.outputs" 
        :key="output.id" 
        class="flow-node-output-item"
      >
        <span class="flow-node-output-label">{{ output.label }}</span>
        <span class="flow-node-output-type">{{ output.valueType }}</span>
      </div>
    </div>

  </div>
</template>

<style scoped>
@import '@/components/flow/styles/NodeBase.css';
</style>

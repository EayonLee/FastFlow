<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import FlowSelect from '@/components/flow/controls/FlowSelect.vue'
import FlowTextarea from '@/components/flow/controls/FlowTextarea.vue'
import FlowNumberInput from '@/components/flow/controls/FlowNumberInput.vue'
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

// Helpers for input types
const isHidden = (input: NodeInput) => {
  return input.renderTypeList?.includes('hidden')
}

const isTextarea = (input: NodeInput) => {
  return input.renderTypeList?.includes('textarea')
}

const isLLMModel = (input: NodeInput) => {
  return input.renderTypeList?.includes('settingLLMModel')
}

const isNumber = (input: NodeInput) => {
  return input.renderTypeList?.includes('numberInput') || input.valueType === 'number'
}

const isBoolean = (input: NodeInput) => {
  return input.valueType === 'boolean'
}

const isDatasetQuote = (input: NodeInput) => {
  return input.renderTypeList?.includes('settingDatasetQuotePrompt')
}
</script>

<template>
  <div class="flow-node-card" :class="{ selected }">
    <div class="flow-node-icon-container">
      <span class="flow-node-icon">{{ data.icon || '🤖' }}</span>
    </div>
    <div class="flow-node-title">{{ nodeName }}</div>
    <div class="flow-node-desc" v-if="intro" :title="intro">{{ intro }}</div>

    <!-- Dynamic Inputs -->
    <div class="flow-node-inputs" v-if="data.inputs && data.inputs.length">
      <div class="flow-node-inputs-header">{{ t('editor.inputs') }}</div>
      
      <div class="flow-node-list-container">
      <div 
        v-for="input in data.inputs"  
        :key="input.key" 
        class="flow-node-input-item"
        v-show="!isHidden(input) && input.key !== 'stringQuoteText'"
      >
        <div class="flow-node-input-label">
          <div class="label-text">
            {{ input.label || input.key }} 
            <span v-if="input.required" style="color: #ff4d4f">*</span>
            <!-- Description Tooltip -->
            <div v-if="input.description" class="tooltip-container">
              <span class="info-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="16" x2="12" y2="12"></line>
                  <line x1="12" y1="8" x2="12.01" y2="8"></line>
                </svg>
              </span>
              <div class="tooltip-text">{{ input.description }}</div>
            </div>
          </div>
        </div>
        
        <!-- LLM Model Selector -->
        <FlowSelect 
           v-if="isLLMModel(input)"
           :modelValue="input.selected || (Array.isArray(input.value) ? input.value[0] : input.value)"
           :options="Array.isArray(input.value) ? input.value : [input.value]"
           @update:modelValue="(val) => input.selected = val"
           class="nodrag"
        />

        <!-- Dataset Quote (Safety Knowledge Base) -->
        <div v-else-if="isDatasetQuote(input)" class="flow-node-quote-picker nodrag">
           <FlowSelect 
             :modelValue="''" 
             :options="[{label: '暂无知识库', value: ''}]" 
             disabled 
           />
        </div>

        <!-- Textarea Renderer -->
        <FlowTextarea
          v-else-if="isTextarea(input)"
          v-model="input.value"
          :placeholder="input.placeholder || input.description || ''"
          :rows="input.key === 'systemPrompt' || input.key === 'userChatInput' ? 6 : 3"
          :label="input.label || input.key"
        />
        
        <!-- Number Input (History) -->
        <FlowNumberInput
          v-else-if="isNumber(input)"
          :modelValue="input.value"
          :min="input.min"
          :max="input.max"
          :step="input.step"
          :placeholder="input.placeholder || input.description || ''"
          @update:modelValue="(val) => input.value = val"
        />

         <!-- Boolean Input (Toggle) -->
         <div v-else-if="isBoolean(input)" class="flow-node-boolean nodrag">
            <label class="switch">
              <input type="checkbox" v-model="input.value">
              <span class="slider round"></span>
            </label>
         </div>
        
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
    </div>

    <!-- Dynamic Outputs -->
    <div class="flow-node-outputs" v-if="data.outputs && data.outputs.length">
      <div class="flow-node-outputs-header">{{ t('editor.outputs') }}</div>
      
      <div class="flow-node-list-container">
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

    <Handle 
      :id="`${id}-target-left`"
      type="target" 
      :position="Position.Left" 
      class="flow-node-handle"
    />
    <Handle 
      :id="`${id}-source-right`"
      type="source" 
      :position="Position.Right" 
      class="flow-node-handle"
    />
  </div>
</template>

<style scoped>
@import '@/components/flow/styles/NodeBase.css';

.flow-node-quote-picker {
  display: flex;
  align-items: center;
  padding: 0;
  border: none;
  background: transparent;
  width: 100%;
}
</style>

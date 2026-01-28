<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkflowNodeStore } from '@/stores/workflowNodeStore'

const { t } = useI18n()
const workflowNodeStore = useWorkflowNodeStore()
const isCollapsed = ref(true)

onMounted(() => {
  workflowNodeStore.fetchNodes()
})

const toggle = () => {
  isCollapsed.value = !isCollapsed.value
}

const onDragStart = (event: DragEvent, node: any) => {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/vueflow', JSON.stringify(node))
    event.dataTransfer.effectAllowed = 'move'
  }
}

const nodes = computed(() => {
  return workflowNodeStore.nodeRegistry.map((node: any) => ({
    ...node,
    label: node.name
  }))
})
</script>

<template>
  <div class="node-palette" :class="{ collapsed: isCollapsed }">
    <div class="palette-header" @click="toggle">
      <span class="title" v-if="!isCollapsed">{{ t('editor.nodes') }}</span>
      <span class="toggle-icon">{{ isCollapsed ? '›' : '‹' }}</span>
    </div>
    
    <div class="node-list" v-show="!isCollapsed">
      <div 
        v-for="node in nodes" 
        :key="node.flowNodeType" 
        class="node-item"
        draggable="true"
        @dragstart="onDragStart($event, node)"
      >
        <span class="node-icon">{{ node.icon }}</span>
        <span class="node-label">{{ node.label }}</span>
      </div>
    </div>

    <!-- Vertical text when collapsed -->
    <div class="collapsed-label" v-show="isCollapsed">
      {{ t('editor.nodes') }}
    </div>
  </div>
</template>

<style scoped>
.node-palette {
  position: absolute;
  top: 20px;
  bottom: 100px; /* Increased to avoid covering controls */
  left: 20px;
  width: 200px;
  background: rgba(10, 10, 10, 0.95);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  backdrop-filter: blur(10px);
  z-index: 100;
  transition: width 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.node-palette.collapsed {
  width: 40px;
  cursor: pointer;
}

.palette-header:hover {
  background: rgba(0, 255, 65, 0.05);
  border-bottom-color: var(--accent-neon);
}

.palette-header:hover .title,
.palette-header:hover .toggle-icon {
  color: var(--accent-neon);
}

.node-palette.collapsed:hover {
  border-color: var(--accent-neon);
  box-shadow: 0 0 15px rgba(0, 255, 65, 0.1);
}

.node-palette.collapsed:hover .collapsed-label,
.node-palette.collapsed:hover .toggle-icon {
  color: var(--accent-neon);
}

.palette-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  height: 45px;
  flex-shrink: 0; /* Prevent header from shrinking */
}

.node-palette.collapsed .palette-header {
  padding: 12px 0;
  justify-content: center;
}

.title {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  letter-spacing: 1px;
  font-weight: 600;
}

.toggle-icon {
  color: var(--text-dim);
  font-size: 16px;
  transition: color 0.2s;
}

.node-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.node-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: grab;
  transition: all 0.2s;
  user-select: none;
}

.node-item:hover {
  background: rgba(0, 255, 65, 0.08);
  border-color: var(--accent-neon);
  transform: translateX(2px);
}

.node-item:active {
  cursor: grabbing;
}

.node-icon {
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
}

.node-label {
  font-size: 13px;
  color: var(--text-primary);
}

.node-item:hover .node-label,
.node-item:hover .node-icon {
  color: var(--accent-neon);
}

.collapsed-label {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  color: var(--text-secondary);
  font-size: 12px;
  font-family: var(--font-mono);
  letter-spacing: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding-bottom: 20px;
  text-transform: uppercase;
}
</style>

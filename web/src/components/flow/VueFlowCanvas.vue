<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { Background } from '@vue-flow/background'
import { Controls, ControlButton } from '@vue-flow/controls'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { useI18n } from 'vue-i18n'
import { getDefaultWorkflowCanvas } from '@/services/workflowService'
import UserGuideNode from '@/components/flow/nodes/UserGuide/UserGuideNode.vue'
import WorkflowStartNode from '@/components/flow/nodes/WorkflowStart/WorkflowStartNode.vue'
import ChatNode from '@/components/flow/nodes/Chat/ChatNode.vue'
import TechEdge from '@/components/flow/styles/TechEdge.vue'

const { t } = useI18n()
const { fitView, zoomIn, zoomOut, onNodeDragStop, onConnect, onEdgeUpdateEnd, onPaneReady, project } = useVueFlow()

const nodes = ref<any[]>([])
const edges = ref<any[]>([])

// 拖拽相关处理
const onDragOver = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const onDrop = (event: DragEvent) => {
  const data = event.dataTransfer?.getData('application/vueflow')
  if (!data) return

  try {
    const nodeData = JSON.parse(data)
    
    // 获取画布的边界
    const bounds = (event.currentTarget as Element).getBoundingClientRect()
    
    // 计算相对于画布的坐标
    const position = project({
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
    })

    const newNode = {
      id: `node-${Date.now()}`,
      type: nodeData.flowNodeType,
      position,
      data: { ...nodeData }
    }

    nodes.value.push(newNode)
    saveHistory()
  } catch (err) {
    console.error('Failed to drop node:', err)
  }
}

onMounted(async () => {
  if (nodes.value.length === 0) {
    // 从后端获取默认画布配置
    const defaultCanvas = await getDefaultWorkflowCanvas()
    if (defaultCanvas) {
      // 映射后端数据结构到 Vue Flow 格式
      nodes.value = (defaultCanvas.nodes || []).map((node: any) => ({
        id: node.nodeId,
        type: node.flowNodeType,
        position: node.position,
        data: { ...node }
      }))
      edges.value = defaultCanvas.edges || []
      // 记录初始状态
      saveHistory()
    }
  }
})


// 画布交互模式：缩放 vs 移动
const panOnScroll = ref(false) // false = 滚轮缩放, true = 滚轮平移
const toggleMode = () => {
  panOnScroll.value = !panOnScroll.value
}

// 简易撤销/重做
const history = ref<string[]>([])
const historyIndex = ref(-1)
const isUndoRedo = ref(false)

// 记录当前状态到历史记录
const saveHistory = () => {
  if (isUndoRedo.value) return
  
  try {
    const snapshot = JSON.stringify({ nodes: nodes.value, edges: edges.value })
    // 避免重复记录
    if (historyIndex.value >= 0 && history.value[historyIndex.value] === snapshot) return

    // 如果在撤销状态下操作，丢弃未来的记录
    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1)
    }
    
    history.value.push(snapshot)
    historyIndex.value++
    
    // 限制历史记录长度
    if (history.value.length > 20) {
      history.value.shift()
      historyIndex.value--
    }
  } catch (err) {
    console.error('Failed to save history:', err)
  }
}

// 记录初始状态
saveHistory()

// 监听画布核心事件
onNodeDragStop(() => saveHistory())
onConnect(() => saveHistory())
onEdgeUpdateEnd(() => saveHistory())

// 仅监听节点/连线数量变化（增删）
watch(() => [nodes.value.length, edges.value.length], () => {
  saveHistory()
})

// 撤销操作
const undo = () => {
  if (historyIndex.value > 0) {
    isUndoRedo.value = true
    historyIndex.value--
    const snapshot = JSON.parse(history.value[historyIndex.value] || '{}')
    nodes.value = snapshot.nodes
    edges.value = snapshot.edges
    // 给 Vue 一点时间更新 DOM
    setTimeout(() => { isUndoRedo.value = false }, 100)
  }
}

// 重做操作
const redo = () => {
  if (historyIndex.value < history.value.length - 1) {
    isUndoRedo.value = true
    historyIndex.value++
    const snapshot = JSON.parse(history.value[historyIndex.value] || '{}')
    nodes.value = snapshot.nodes
    edges.value = snapshot.edges
    setTimeout(() => { isUndoRedo.value = false }, 100)
  }
}

// 初始化时自动适配视图
onPaneReady(() => {
  fitView()
})

// 暴露节点和边给父组件
defineExpose({
  nodes,
  edges,
  fitView
})

</script>

<template>
  <div class="vue-flow-wrapper">
    <VueFlow 
      v-model:nodes="nodes"
      v-model:edges="edges" 
      class="basic-flow"
      :pan-on-scroll="panOnScroll"
      :zoom-on-scroll="!panOnScroll"
      @dragover="onDragOver"
      @drop="onDrop"
    >
      <template #node-userGuide="props">
        <UserGuideNode v-bind="props" />
      </template>
      <template #node-workflowStart="props">
        <WorkflowStartNode v-bind="props" />
      </template>
      <template #node-chatNode="props">
        <ChatNode v-bind="props" />
      </template>

      <template #edge-tech="props">
        <TechEdge v-bind="props" />
      </template>
      
      <Background pattern-color="#555" :gap="20" />
      <Controls 
        :show-interactive="false" 
        :show-zoom="false" 
        :show-fit-view="false"
        class="custom-controls"
      >
        <!-- History Group -->
        <ControlButton @click="undo" :data-title="t('editor.undo')" :disabled="historyIndex <= 0">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>
        </ControlButton>
        <ControlButton @click="redo" :data-title="t('editor.redo')" :disabled="historyIndex >= history.length - 1">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3L21 13"/></svg>
        </ControlButton>
        
        <div class="control-separator">|</div>

        <!-- View Group -->
        <ControlButton @click="zoomIn" :data-title="t('editor.zoom_in')">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
        </ControlButton>
        <ControlButton @click="zoomOut" :data-title="t('editor.zoom_out')">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
        </ControlButton>
        
        <div class="control-separator">|</div>

        <ControlButton @click="fitView" :data-title="t('editor.fit_view')">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>
        </ControlButton>

        <div class="control-separator">|</div>

        <!-- Mode Group -->
        <ControlButton @click="toggleMode" :data-title="panOnScroll ? t('editor.touch_mode') : t('editor.mouse_mode')">
          <svg v-if="!panOnScroll" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="7"/><path d="M12 2v6"/></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M2 14h20"/><path d="M12 14v6"/></svg>
        </ControlButton>
      </Controls>
    </VueFlow>
  </div>
</template>

<style>
/* Vue Flow Global Overrides for Dark Theme */
.vue-flow-wrapper {
  width: 100%;
  height: 100%;
  background: var(--bg-app);
}

/* Green Accent - Hover */
.vue-flow__node:hover,
.vue-flow__node-default:hover,
.vue-flow__node-input:hover,
.vue-flow__node-output:hover,
.vue-flow__node-system-config:hover {
  border-color: var(--accent-neon) !important;
  box-shadow: 0 0 18px rgba(0, 255, 65, 0.4);
}

.vue-flow__handle {
  width: 8px;
  height: 8px;
  background: #000;
  border: 1px solid #666;
}

.vue-flow__handle:hover {
  background: var(--accent-neon);
  border-color: var(--accent-neon);
}

.vue-flow__edge-path {
  stroke: var(--text-secondary);
  stroke-width: 2;
}

.vue-flow__edge.selected .vue-flow__edge-path {
  stroke: var(--accent-neon);
}

/* Controls */
.vue-flow__controls {
  display: flex;
  flex-direction: row;
  align-items: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 4px 8px;
  background: var(--bg-panel);
  gap: 2px;
}

.control-separator {
  color: var(--text-dim);
  font-family: var(--font-mono);
  font-size: 14px;
  margin: 0 4px;
  user-select: none;
  font-weight: 300;
  opacity: 0.5;
}

.vue-flow__controls-button {
  background: transparent;
  border: none;
  border-radius: 4px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  fill: currentColor;
  transition: all 0.2s;
  padding: 0;
  cursor: pointer;
  position: relative;
}

.vue-flow__controls-button[data-title]:hover::after {
  content: attr(data-title);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-bottom: 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
  z-index: 100;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  pointer-events: none;
}

.vue-flow__controls-button:hover {
  background: var(--bg-node);
  color: var(--text-primary);
  fill: currentColor;
}

.vue-flow__controls-button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.control-icon {
  font-size: 14px;
  line-height: 1;
}
</style>

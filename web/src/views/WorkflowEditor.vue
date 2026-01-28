<script setup lang="ts">
/**
 * 工作流编辑器视图
 * 
 * 核心职责：
 * 1. 组装三大板块：左侧节点库、中间画布、右侧AI助手
 * 2. 管理工作流的加载(LocalStorage)、导出(JSON)、导入(JSON)
 * 3. 处理复杂的 UI 交互，比如 AI 面板的拖拽改变宽度
 */
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import WorkbenchLayout from '@/layouts/WorkbenchLayout.vue'
import VueFlowCanvas from '@/components/flow/VueFlowCanvas.vue'
import NodePalette from '@/components/flow/NodePalette.vue'
import AIChatPanel from '@/components/chat/AIChatPanel.vue'
import FlowModal from '@/components/common/FlowModal.vue'
import CodeEditor from '@/components/common/CodeEditor.vue'
import { exportWorkflow } from '@/components/flow/serialization/exporter'
import { useToast } from '@/composables/useToast'
import { getWorkflow } from '@/services/workflowService'
import { useWorkflowNodeStore } from '@/stores/workflowNodeStore'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const { showToast } = useToast()
const workflowNodeStore = useWorkflowNodeStore()

// 当前工作流的元数据，先给个空壳
const workflow = ref({
  id: '', // 工作流ID
  name: '', // 工作流名称
  description: '' // 工作流描述
})

// 画布组件的引用，导出数据全靠它
const vueFlowCanvasRef = ref()

/**
 * 导出工作流配置
 * 把画布上的节点/连线序列化成 JSON，直接塞用户剪贴板里
 */
const handleExport = async () => {
  // 画布还没挂载好
  if (!vueFlowCanvasRef.value) return

  // 优先使用 getGraphSnapshot 获取当前快照，比直接访问 ref 更稳
  let nodesData = []
  let edgesData = []

  if (vueFlowCanvasRef.value.getGraphSnapshot) {
    const snapshot = vueFlowCanvasRef.value.getGraphSnapshot()
    nodesData = snapshot.nodes || []
    edgesData = snapshot.edges || []
  } else {
    // Fallback: 兼容直接访问属性的情况 (Vue 3 defineExpose 可能会自动解包 ref)
    const rawNodes = vueFlowCanvasRef.value.nodes
    const rawEdges = vueFlowCanvasRef.value.edges
    nodesData = Array.isArray(rawNodes) ? rawNodes : (rawNodes?.value || [])
    edgesData = Array.isArray(rawEdges) ? rawEdges : (rawEdges?.value || [])
  }

  console.log('[WorkflowEditor] Exporting nodes:', nodesData)
  console.log('[WorkflowEditor] Exporting edges:', edgesData)
  
  try {
    // 走统一的导出逻辑，把动态数据和静态配置缝合一下
    const json = exportWorkflow(nodesData, edgesData, workflowNodeStore.nodeRegistry, workflow.value)
    const jsonString = JSON.stringify(json, null, 2)
    
    // 浏览器剪贴板 Nexus
    await navigator.clipboard.writeText(jsonString)
    
    // 使用统一的 Toast 反馈
    showToast(t('common.export_success') || 'Exported to clipboard successfully!', 'success')
    
    // 完事把菜单关了
    isImportExportOpen.value = false
  } catch (err: any) {
    console.error('Export workflow config failed:', err)
    // 错误也用统一的 Toast，并展示具体错误信息
    showToast(`Export workflow config failed: ${err.message || err}`, 'error')
  }
}

/**
 * 初始化加载工作流
 * 从 Nexus 获取数据
 */
const loadWorkflow = async () => {
  const id = route.params.id as string
  try {
    const data = await getWorkflow(id)
    if (data) {
      workflow.value = {
        id: data.id,
        name: data.name || '',
        description: data.description || ''
      }

      // 如果有保存的配置，则使用保存的配置渲染画布
      if (data.config && vueFlowCanvasRef.value) {
        try {
          const flowData = JSON.parse(data.config)
          // 确保包含 nodes 和 edges 才能覆盖
          if (Array.isArray(flowData.nodes) && Array.isArray(flowData.edges)) {
            vueFlowCanvasRef.value.setGraph?.(flowData.nodes, flowData.edges)
            
            // 等待 DOM 更新后适配视图
            nextTick(() => {
              vueFlowCanvasRef.value.fitView?.()
            })
          }
        } catch (err) {
          console.error('Failed to parse workflow config:', err)
          // 解析失败则保持默认初始化节点，不中断流程
        }
      }
    }
  } catch (e) {
    console.error('Failed to load workflow', e)
    showToast(t('common.load_failed') || 'Failed to load workflow', 'error')
  }
}

// AI 面板相关的 UI 状态
const isAiPanelOpen = ref(false) // 默认关着，省空间
const drawerWidth = ref(600)     // AI聊天面板默认展开宽度
const isResizing = ref(false)    // 标记正在拖拽中，避免冲突
const isImportExportOpen = ref(false) // 导入导出菜单开关
const isImportModalOpen = ref(false) // 导入模态窗开关
const importJsonContent = ref('') // 导入的 JSON 内容

const aiChatPanelRef = ref() // 引用 AI 聊天面板组件

const toggleAiPanel = async () => {
  isAiPanelOpen.value = !isAiPanelOpen.value
  if (isAiPanelOpen.value) {
    await nextTick()
    setTimeout(() => {
      aiChatPanelRef.value?.focusInput()
    }, 300) // 延迟等待抽屉动画
  }
}

/**
 * 打开导入模态窗
 */
const openImportModal = () => {
  importJsonContent.value = ''
  isImportModalOpen.value = true
  isImportExportOpen.value = false // 关闭下拉菜单
}

/**
 * 关闭导入模态窗
 */
const closeImportModal = () => {
  isImportModalOpen.value = false
}

/**
 * 确认导入工作流
 * 解析用户输入的 JSON 并更新画布
 */
const handleImportWorkflow = () => {
  try {
    if (!importJsonContent.value.trim()) {
      showToast(t('common.import_empty'), 'warning')
      return
    }

    const flowData = JSON.parse(importJsonContent.value)
    
    // 简单的格式校验
    if (!Array.isArray(flowData.nodes) || !Array.isArray(flowData.edges)) {
      throw new Error('Invalid workflow format: missing nodes or edges array')
    }

    if (vueFlowCanvasRef.value) {
      showToast(t('common.import_success'), 'success')
      closeImportModal()
      
      // 等待模态窗关闭动画完成后再渲染画布，避免UI卡顿
      setTimeout(() => {
        if (vueFlowCanvasRef.value) {
          // 确保节点类型字段匹配：将 flowNodeType 映射到 type
          const nodes = flowData.nodes.map((node: any) => ({
            ...node,
            id: node.nodeId || node.id, // 兼容 nodeId 和 id
            type: node.flowNodeType || node.type, // 兼容 flowNodeType 和 type
            data: {
              ...node, // 将所有属性都放到 data 中，以便组件可以访问
              ...node.data // 如果原本就有 data，覆盖之
            }
          }))

          // 使用子组件暴露的 setGraph，保证状态更新一致
          
          // 确保边使用自定义的 tech 类型以保持特效
          const edges = flowData.edges.map((edge: any) => ({
            ...edge,
            type: edge.type || 'tech', // 如果没有指定类型，默认为 tech
            animated: true // 强制开启流光动画
          }))
          
          vueFlowCanvasRef.value.setGraph?.(nodes, edges)
          
          // 等待 DOM 更新节点尺寸后，执行自适应视图
          nextTick(() => {
            setTimeout(() => {
              vueFlowCanvasRef.value.fitView?.({ 
                padding: 0.2, 
                duration: 800,
                includeHiddenNodes: true 
              })
            }, 100)
          })
        }
      }, 300)
    }
  } catch (err: any) {
    console.error('Import failed:', err)
    showToast(`Import failed: ${err.message}`, 'error')
  }
}

/**
 * 获取当前画布的图数据
 * 供 AI 助手获取上下文使用
 */
const getGraphData = async () => {
  if (!vueFlowCanvasRef.value) return { nodes: [], edges: [] }
  const snap = vueFlowCanvasRef.value.getGraphSnapshot?.()
  if (snap) return { nodes: snap.nodes, edges: snap.edges }
  const { nodes, edges } = vueFlowCanvasRef.value
  return { nodes: nodes?.value ?? [], edges: edges?.value ?? [] }
}

/**
 * 处理 AI 助手发来的图更新请求
 * 包括布局更新和全量图更新
 */
const handleGraphUpdate = (payload: { type: 'layout' | 'graph', data: any }) => {
  if (!vueFlowCanvasRef.value) return

  try {
    if (payload.type === 'layout') {
      console.log('[WorkflowEditor] Received layout update content:', payload.data)
      // 布局更新：仅更新节点位置
      const positions = payload.data
      vueFlowCanvasRef.value.applyLayout?.(positions)
      
      nextTick(() => {
        vueFlowCanvasRef.value.fitView?.({ duration: 800 })
      })
      
    } else if (payload.type === 'graph') {
      const graphData = payload.data
      if (graphData.nodes && graphData.edges) {
        console.log('[WorkflowEditor] Received graph update content:', graphData)
        // 转换节点格式以适配 VueFlow
        const nodes = graphData.nodes.map((n: any) => ({
          id: n.id,
          // 确保使用 flowNodeType 或 type 映射到 VueFlow 的 type
          type: n.type || n.flowNodeType || (n.data && n.data.flowNodeType),
          position: (n.data && n.data.position) || { x: 0, y: 0 },
          data: { 
            ...n,
            ...(n.data || {}), 
            label: n.label || (n.data && n.data.name)
          },
          label: n.label || n.name || (n.data && n.data.name)
        }))
        
        const edges = graphData.edges.map((e: any) => ({
          id: e.id || `e${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          sourceHandle: e.source_handle,
          targetHandle: e.target_handle,
          type: 'tech',
          animated: true
        }))
        
        vueFlowCanvasRef.value.setGraph?.(nodes, edges)
        
        nextTick(() => {
          // 渲染完成后自动触发自动布局，覆盖模型生成的坐标
          if (vueFlowCanvasRef.value.autoLayout) {
            console.log('[WorkflowEditor] Triggering auto-layout after graph update')
            vueFlowCanvasRef.value.autoLayout()
          } else {
            // Fallback: 如果没有 autoLayout，就只 fitView
            vueFlowCanvasRef.value.fitView?.({ duration: 800 })
          }
        })
      }
    }
  } catch (err) {
    console.error('Failed to update graph from Nexus:', err)
    showToast('Failed to update graph', 'error')
  }
}

/**
 * 开始拖拽调整宽度
 * 鼠标按下时触发，挂载全局监听
 */
const startResize = () => {
  isResizing.value = true
  // 必须挂在 document 上，不然拖快了鼠标出界会断触
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', stopResize)
  // 强制光标样式，防止选中文字
  document.body.style.cursor = 'ew-resize'
  document.body.style.userSelect = 'none'
}

/**
 * 拖拽进行中
 * 核心算宽逻辑
 */
const handleMouseMove = (e: MouseEvent) => {
  if (!isResizing.value) return
  
  // 算法：屏幕总宽 - 鼠标当前X坐标 = 右侧抽屉宽度
  const newWidth = window.innerWidth - e.clientX
  
  // 做了个钳位，太窄(300)没法看，太宽(800)遮住画布了
  if (newWidth >= 300 && newWidth <= 800) {
    drawerWidth.value = newWidth
  }
}

/**
 * 结束拖拽
 * 打扫战场，卸载监听
 */
const stopResize = () => {
  isResizing.value = false
  document.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('mouseup', stopResize)
  // 还原样式
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

const toggleImportExport = () => {
  isImportExportOpen.value = !isImportExportOpen.value
}

/**
 * 处理点击外部关闭菜单
 * 经典的点击穿透处理
 */
const handleDocumentClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  // 如果点的不是菜单里面的东西，就关掉菜单
  if (!target.closest('.wf-import-export')) {
    isImportExportOpen.value = false
  }
}

onMounted(() => {
  loadWorkflow()
  // 挂个全局点击监听，处理各种下拉菜单的关闭
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  // 组件销毁前必须解绑，防止内存泄漏
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<template>
  <!-- 复用通用的工作台布局，自带侧边栏 -->
  <WorkbenchLayout>
    <!-- 顶部导航栏右侧的扩展区域 -->
    <template #header-extra>
      <div class="wf-header">
        <!-- 左侧：工作流基本信息 -->
        <div class="wf-info">
          <div class="wf-title-row">
            <span class="wf-name">{{ workflow.name || t('workflow.untitled') }}</span>
          </div>
          <span class="wf-desc">{{ workflow.description || t('workflow.description') }}</span>
        </div>
        
        <!-- 右侧：操作按钮组 -->
        <div class="wf-actions">
          
          <!-- 导入导出按钮 (带下拉菜单) -->
          <div class="wf-import-export">
            <!-- 加了 .stop 防止冒泡触发 document 的关闭逻辑 -->
            <button class="btn secondary import-export-btn" @click.stop="toggleImportExport">
              <span class="ie-icon">⇅</span>
              <span class="caret">▾</span>
            </button>
            
            <!-- 下拉菜单本体 -->
            <div v-if="isImportExportOpen" class="import-export-menu">
              <button class="import-export-item" type="button" @click="openImportModal">
                {{ t('common.import') }}
              </button>
              <button class="import-export-item" type="button" @click="handleExport">
                {{ t('common.export') }}
              </button>
            </div>
          </div>

          <!-- 返回列表 -->
          <button class="btn secondary" @click="router.push('/workflows')">
            {{ t('common.back') }}
          </button>
          
          <!-- 保存 (目前是装饰品，逻辑待接) -->
          <button class="btn-neon save-btn">
            {{ t('common.save') }}
          </button>

        </div>
      </div>
    </template>

    <!-- 主编辑区：Flex 布局，左中右结构 -->
    <div class="editor-container">
      <!-- 左侧：节点库 (Palette) -->
      <NodePalette />
      
      <!-- 中间：核心画布 -->
      <div class="canvas-area">
        <!-- ref 绑定，为了方便父组件调用子组件方法 -->
        <VueFlowCanvas ref="vueFlowCanvasRef" />
      </div>

      <!-- 右侧：AI 助手抽屉 -->
      <div 
        class="ai-drawer" 
        :class="{ closed: !isAiPanelOpen, resizing: isResizing }"
        :style="{ width: isAiPanelOpen ? `${drawerWidth}px` : '0px' }"
      >
        <!-- 拖拽手柄 -->
        <div class="resizer" @mousedown.prevent="startResize" v-show="isAiPanelOpen"></div>
        
        <!-- 开关按钮，挂在抽屉边上 -->
        <div class="drawer-toggle" @click="toggleAiPanel" :title="isAiPanelOpen ? 'Close AI Panel' : 'Open AI Agent'">
          <span class="toggle-icon">{{ isAiPanelOpen ? '→' : '🤖' }}</span>
        </div>
        
        <!-- AI 聊天面板内容 -->
        <div class="drawer-content" v-show="isAiPanelOpen">
          <AIChatPanel 
            ref="aiChatPanelRef"
            class="embedded-chat"
            :get-graph-data="getGraphData"
            @update-graph="handleGraphUpdate"
          />
        </div>
      </div>
    </div>

    <!-- 导入工作流模态窗 -->
    <FlowModal 
      :visible="isImportModalOpen" 
      :title="t('common.import_workflow')"
      width="1000px"
      @close="closeImportModal"
    >
      <div class="import-modal-content">
        <p class="import-tip">
          {{ t('common.import_tip') }}
        </p>
        <CodeEditor
          v-model="importJsonContent"
          height="500px"
        />
      </div>
      
      <template #footer>
        <div class="modal-actions">
          <button class="btn secondary" @click="closeImportModal">
            {{ t('common.cancel') }}
          </button>
          <button class="btn primary" @click="handleImportWorkflow">
            {{ t('common.import') }}
          </button>
        </div>
      </template>
    </FlowModal>
  </WorkbenchLayout>
</template>

<style scoped>
/* 撑满容器，不然画布显示不全 */
.editor-container {
  display: flex;
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

/* 头部样式：两端对齐 */
.wf-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 24px;
}

/* 信息区：左对齐，垂直排列 */
.wf-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
}

.wf-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wf-name {
  font-weight: 600;
  font-size: 16px;
  color: var(--text-primary);
}

.wf-status-badge {
  font-size: 10px;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.wf-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.wf-actions {
  display: flex;
  gap: 12px;
}

/* 导入导出菜单容器 */
.wf-import-export {
  position: relative;
  display: flex;
}

.import-export-btn {
  gap: 8px;
  padding: 0 18px;
  height: 34px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.2px;
}

.ie-icon {
  font-size: 14px;
  line-height: 1;
  opacity: 0.9;
}

.ie-text {
  line-height: 1;
}

.caret {
  font-size: 12px;
  opacity: 0.7;
}

/* 下拉菜单样式 */
.import-export-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  min-width: 140px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5);
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 10;
}

.import-export-item {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-primary);
  padding: 9px 12px;
  font-size: 14px;
  border-radius: 6px;
  text-align: left;
  cursor: pointer;
}

/* 菜单项 Hover 效果：霓虹绿 */
.import-export-item:hover,
.import-export-item:focus,
.import-export-item:focus-visible,
.import-export-item:active {
  background: rgba(0, 255, 65, 0.08);
  border-color: var(--accent-neon);
  color: var(--accent-neon);
  box-shadow: 0 0 0 1px rgba(0, 255, 65, 0.35);
  outline: none;
}

/* 通用按钮样式 */
.btn {
  height: 32px;
  padding: 0 16px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-ui);
}

.btn.secondary {
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
}

.btn.secondary:hover {
  border-color: var(--text-secondary);
  background: var(--bg-panel);
}

.btn.primary {
  background: var(--accent-neon);
  border: 1px solid var(--accent-neon);
  color: #000;
  font-weight: 600;
}

.btn.primary:hover {
  background: var(--accent-neon-dim);
  box-shadow: 0 0 10px rgba(0, 255, 65, 0.3);
}

.canvas-area {
  flex: 1;
  position: relative;
  height: 100%;
}

/* AI 抽屉样式 */
.ai-drawer {
  /* 宽度由 JS 动态控制 */
  height: 100%;
  background: var(--bg-panel);
  border-left: 1px solid var(--border-subtle);
  /* 加上过渡动画，丝滑一点 */
  transition: width 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  position: relative;
  display: flex;
  flex-direction: column;
}

/* 拖拽时禁用过渡，不然会卡顿 */
.ai-drawer.resizing {
  transition: none;
  border-left-color: var(--accent-neon);
}

.ai-drawer.closed {
  width: 0 !important;
  border-left: none;
}

/* 拖拽手柄热区 */
.resizer {
  position: absolute;
  left: 0;
  top: 0;
  width: 4px;
  height: 100%;
  cursor: ew-resize;
  z-index: 100;
  background: transparent;
  transition: background 0.2s;
}

.resizer:hover, 
.ai-drawer.resizing .resizer {
  background: var(--accent-neon);
}

/* 抽屉开关按钮 */
.drawer-toggle {
  position: absolute;
  top: 50%;
  left: -28px; /* 悬浮在抽屉外侧 */
  width: 28px;
  height: 48px;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-right: none;
  border-radius: 8px 0 0 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 14px;
  z-index: 10;
  box-shadow: -2px 0 10px rgba(0,0,0,0.1);
}

.drawer-toggle:hover {
  color: var(--accent-neon);
  background: var(--bg-node);
  border-color: var(--accent-neon);
  box-shadow: -2px 0 10px rgba(0, 255, 65, 0.2);
}

.drawer-content {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

/* 强制覆盖 AI 面板样式以适应抽屉 */
:deep(.ai-chat-panel.embedded-chat) {
  position: static;
  width: 100%;
  height: 100%;
  border: none;
  border-radius: 0;
  box-shadow: none;
}

/* Import Modal Styles */
.import-modal-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.import-tip {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}
</style>

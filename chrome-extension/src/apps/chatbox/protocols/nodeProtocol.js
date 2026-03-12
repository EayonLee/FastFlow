import { Bridge } from '@/extension/runtime/bridge.js'
import { createProtocolTokenNode, createTriggerRegex, normalizeString } from './common.js'

/**
 * Node 协议定义：
 * - trigger: #
 * - token: selected_node(<node_id>)
 * - 数据源: 当前画布导出的 workflow_graph
 */
const MODE = 'node'
const TOKEN_NODE_NAME = 'protocolNodeToken'

const tokenNode = createProtocolTokenNode({
  nodeName: TOKEN_NODE_NAME,
  dataAttr: 'data-protocol-node-token',
  cssClass: 'composer-node-chip',
  attrs: {
    nodeId: {
      default: '',
    },
    label: {
      default: '',
    },
  },
  getLabel: (attrs) => String(attrs.label || attrs.nodeId || ''),
  serializeText: (attrs) => `selected_node(${String(attrs.nodeId || '')})`,
})

function parseWorkflowGraphPayload(rawGraph) {
  if (typeof rawGraph === 'string') {
    const parsed = JSON.parse(rawGraph)
    if (parsed && typeof parsed === 'object') return parsed
    return {}
  }
  if (rawGraph && typeof rawGraph === 'object') {
    return rawGraph
  }
  return {}
}

function buildNodeItems(rawGraph) {
  const workflowGraph = parseWorkflowGraphPayload(rawGraph)
  const nodes = Array.isArray(workflowGraph?.nodes) ? workflowGraph.nodes : []
  const items = []

  for (const node of nodes) {
    const nodeId = normalizeString(node?.nodeId)
    const name = normalizeString(node?.name)
    const nodeType = normalizeString(node?.flowNodeType)
    if (!nodeId || !name) continue

    items.push({
      nodeId,
      name,
      nodeType,
      label: `${name} · ${nodeId}`,
    })
  }

  return items
}

function mapNodeOption(rawItem) {
  const nodeId = normalizeString(rawItem?.nodeId)
  const nodeName = normalizeString(rawItem?.name)
  if (!nodeId || !nodeName) return null

  return {
    key: nodeId,
    leftLabel: nodeName,
    rightLabel: nodeId,
    rightClass: 'node-id',
    rightTitle: nodeId,
    disabled: false,
    payload: rawItem,
  }
}

function filterNodeOption(option, query) {
  const normalizedQuery = normalizeString(query).toLowerCase()
  if (!normalizedQuery) return true

  const nodeName = normalizeString(option?.payload?.name).toLowerCase()
  const nodeId = normalizeString(option?.payload?.nodeId).toLowerCase()
  const nodeType = normalizeString(option?.payload?.nodeType).toLowerCase()
  return nodeName.includes(normalizedQuery)
    || nodeId.includes(normalizedQuery)
    || nodeType.includes(normalizedQuery)
}

async function loadNodeItems() {
  const rawGraph = await Bridge.exportWorkflowGraph()
  return buildNodeItems(rawGraph)
}

// 注册到协议内核的 node 实现。
export const nodeProtocol = {
  mode: MODE,
  triggerChar: '#',
  triggerRegex: createTriggerRegex('#', '[^\\s#\\/\\(\\)]*', ''),
  reloadOnOpen: true,
  tokenNodeName: TOKEN_NODE_NAME,
  tokenNode,
  panel: {
    title: 'NODES',
    badge: 'Canvas',
    loadingText: '读取画布节点中...',
    emptyText: '没有可引用节点',
    hintText: '可直接在输入框输入 # 快速唤起',
    sectionClass: 'nodes-section',
  },
  secondarySection: null,
  async loadItems() {
    return await loadNodeItems()
  },
  toOption(rawItem) {
    return mapNodeOption(rawItem)
  },
  filterOption(option, query) {
    return filterNodeOption(option, query)
  },
  isSelectable(option) {
    return Boolean(option)
  },
  toInsertAttrs(option) {
    const nodeId = normalizeString(option?.payload?.nodeId)
    const nodeName = normalizeString(option?.payload?.name)
    const label = normalizeString(option?.payload?.label || (nodeName ? `${nodeName} · ${nodeId}` : nodeId))
    return {
      nodeId,
      label,
    }
  },
}

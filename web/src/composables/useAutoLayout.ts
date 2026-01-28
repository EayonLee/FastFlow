import dagre from 'dagre'
import { useVueFlow, type Node, type Edge, Position } from '@vue-flow/core'

/**
 * 基于 Dagre 的自动布局 Composable
 * 
 * @param {string} direction - 'TB' (从上到下) 或 'LR' (从左到右)
 */
export function useAutoLayout() {
  const { findNode } = useVueFlow()
  
  const graph = new dagre.graphlib.Graph()
  graph.setGraph({ rankdir: 'LR' }) // 默认为从左到右
  graph.setDefaultEdgeLabel(() => ({}))

  const layout = (nodes: Node[], edges: Edge[], direction = 'LR') => {
    // 1. 配置图对象
    graph.setGraph({ 
      rankdir: direction,
      align: 'UL', // 左上对齐
      nodesep: 50, // 节点横向间距
      ranksep: 80, // 层级纵向间距
      ranker: 'network-simplex' // 可选: 'network-simplex', 'tight-tree', 'longest-path'
    })

    // 2. 将节点添加到 dagre 图中
    nodes.forEach((node) => {
      // 计算布局需要知道节点的尺寸
      // 如果没有尺寸，就给个默认值或者用实际渲染尺寸
      // 注意: Dagre 需要宽高来正确居中边
      const nodeEl = findNode(node.id)
      const width = nodeEl?.dimensions.width || (node as any).dimensions?.width || 200 // 默认宽度
      const height = nodeEl?.dimensions.height || (node as any).dimensions?.height || 80 // 默认高度
      
      graph.setNode(node.id, { width, height })
    })

    // 3. 将边添加到 dagre 图中
    edges.forEach((edge) => {
      graph.setEdge(edge.source, edge.target)
    })

    // 4. 计算布局
    dagre.layout(graph)

    // 5. 应用新坐标
    // 注意: Dagre 返回的是节点中心点，但 Vue Flow 用的是左上角
    return nodes.map((node) => {
      const nodeWithPosition = graph.node(node.id)
      
      // 将中心点坐标转换为左上角坐标
      const newNode = {
        ...node,
        targetPosition: direction === 'LR' ? Position.Left : Position.Top,
        sourcePosition: direction === 'LR' ? Position.Right : Position.Bottom,
        position: {
          x: nodeWithPosition.x - nodeWithPosition.width / 2,
          y: nodeWithPosition.y - nodeWithPosition.height / 2,
        },
      }

      return newNode
    })
  }

  return { layout }
}

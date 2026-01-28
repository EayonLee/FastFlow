/**
 * Workflow Exporter
 * 
 * 核心职责：
 * 负责将编辑器内存中的运行时数据（Nodes/Edges）序列化为可持久化的 JSON 格式。
 * 
 * 设计哲学：
 * 1. Schema-First：以 Registry 中的静态配置为真理来源（Source of Truth），确保导出的数据结构始终符合最新代码定义。
 * 2. 数据清洗：仅保留用户输入的有效 Value，自动剔除过期的字段或临时状态。
 * 3. 隐式迁移：通过 "New Schema + Old Value" 的合并策略，自动兼容旧版本数据。
 */

interface WorkflowInfo {
  id?: string
  name?: string
  description?: string
}

/**
 * 递归处理对象：
 * 1. 过滤 icon 字段，万事通不需要改字段，避免出现错误
 * 2. 将 undefined 转换为 null (保留字段键)
 * 3. 这里的 deepSanitize 会在 JSON.stringify 之前执行，确保 undefined 不会被忽略
 */
const deepSanitize = (obj: any): any => {
  if (obj === undefined) return null
  if (obj === null || typeof obj !== 'object') return obj

  if (Array.isArray(obj)) {
    return obj.map(deepSanitize)
  }

  const res: any = {}
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      // 过滤 icon 字段
      if (key === 'icon') continue
      
      const val = obj[key]
      res[key] = val === undefined ? null : deepSanitize(val)
    }
  }
  return res
}

export const exportWorkflow = (nodes: any[], edges: any[], registry: any[], workflowInfo?: WorkflowInfo) => {
  // 此时 nodes 应该已经是数组了，如果上层传递了 undefined，这里给个默认值防止崩溃
  const safeNodes = Array.isArray(nodes) ? nodes : []
  const safeEdges = Array.isArray(edges) ? edges : []

  const exportNodes = safeNodes.map(node => {
    // 1. 获取基准配置：优先使用 Registry 中的最新 Schema
    const baseConfig = registry.find(n => n.flowNodeType === node.type)
    
    // Fallback：若 Registry 中不存在，直接保留原始数据
    if (!baseConfig) {
      return {
        ...node.data,
        nodeId: node.id,
        position: node.position
      }
    }

    // 2. 解除引用：深拷贝 BaseConfig
    const exportNode = JSON.parse(JSON.stringify(baseConfig))

    // 3. 注入运行时状态
    exportNode.nodeId = node.id
    exportNode.position = node.position
    
    // 覆盖名称
    if (node.data && node.data.name) {
      exportNode.name = node.data.name
    }

    // 4. Inputs 合并策略：Schema (Registry) + Value (Instance)
    if (exportNode.inputs && Array.isArray(exportNode.inputs)) {
      exportNode.inputs = exportNode.inputs.map((baseInput: any) => {
        // 在当前实例里找对应的值
        const currentInput = node.data?.inputs?.find((i: any) => i.key === baseInput.key)
        
        if (currentInput) {
          // 仅合并 value，严格保留 baseInput 的结构定义
          return {
            ...baseInput,
            value: currentInput.value
          }
        }
        // 实例中缺失该字段，直接使用 baseInput (其中已包含 index.ts 定义的默认值)
        return baseInput
      })
    }

    return exportNode
  })

  // 组装最终 JSON
  const finalJson = {
    nodes: exportNodes,
    edges: safeEdges.map(e => ({
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle || `${e.source}-source-right`,
      targetHandle: e.targetHandle || `${e.target}-target-left`
    })),
    chatConfig: {
      variables: [], // TODO: 支持全局变量
      scheduledTriggerConfig: {
        cronString: "",
        timezone: "Asia/Shanghai",
        defaultPrompt: ""
      },
      _id: workflowInfo?.id
    }
  }

  // 统一进行数据清洗
  return deepSanitize(finalJson)
}

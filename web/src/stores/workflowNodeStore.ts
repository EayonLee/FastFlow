import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getWorkflowNodeList, type NodeTypeDefinition } from '@/services/workflowService'

export const useWorkflowNodeStore = defineStore('workflowNode', () => {
  const nodeRegistry = ref<NodeTypeDefinition[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const fetchNodes = async () => {
    if (nodeRegistry.value.length > 0) return

    isLoading.value = true
    error.value = null
    try {
      const nodes = await getWorkflowNodeList()
      nodeRegistry.value = nodes
    } catch (err) {
      error.value = 'Failed to load nodes'
      console.error(err)
    } finally {
      isLoading.value = false
    }
  }

  const getNodeConfig = (type: string) => {
    return nodeRegistry.value.find(n => n.flowNodeType === type)
  }

  return {
    nodeRegistry,
    isLoading,
    error,
    fetchNodes,
    getNodeConfig
  }
})

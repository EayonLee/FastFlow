import apiClient, { type ApiResponse } from './http'

export interface WorkflowRequest {
  description: string
  // 可以根据需要添加更多参数
}

export interface WorkflowResponse {
  id: string
  name: string
  description: string
  creatorName?: string // 创建者昵称
  config?: string
  status?: number
  thumbnail?: string
  createdAt: string
  updatedAt: string
}

export interface NodeInput {
  key: string
  valueType: string
  label: string
  isPro?: boolean
  renderTypeList?: string[]
  value?: any
  required?: boolean
  llmModelType?: string | null
  toolDescription?: string
  debugLabel?: string
  min?: number | null
  max?: number | null
  step?: number | null
  description?: string | null
  placeholder?: string | null
  customInputConfig?: Record<string, any> | null
  canEdit?: boolean
  valueDesc?: string
  selectedTypeIndex?: number
  selected?: any
}

export interface NodeOutput {
  id: string
  key: string
  label: string
  type?: string
  valueType: string
  description?: string
  valueDesc?: string
  required?: boolean
  customFieldConfig?: Record<string, any> | null
}

export interface NodeTypeDefinition {
  nodeId: string
  flowNodeType: string
  name: string // i18n key
  avatar: string
  version: string
  intro?: string
  position: { x: number, y: number }
  inputs: NodeInput[]
  outputs: NodeOutput[]
  icon: string // For UI display
}

export interface CanvasResponse {
  nodes: any[]
  edges: any[]
}

// 生成流程图的 Nexus
export const generateWorkflow = async (request: WorkflowRequest): Promise<WorkflowResponse> => {
  try {
    const response = await apiClient.post<ApiResponse<WorkflowResponse>>('/workflow/generate', request)
    return response.data.data
  } catch (error) {
    throw error
  }
}

// 获取流程图的 Nexus
export const getWorkflow = async (id: string): Promise<WorkflowResponse> => {
  try {
    const response = await apiClient.get<ApiResponse<WorkflowResponse>>(`/workflow/${id}`)
    return response.data.data
  } catch (error) {
    throw error
  }
}

// 创建流程图 Nexus
export const createWorkflow = async (data: any): Promise<any> => {
  try {
    const response = await apiClient.post<ApiResponse<any>>('/workflow/create', data)
    // 后端现在返回的是 data: "uuid-string"，我们需要构造成对象给前端用
    // 或者前端调用处只关心 ID
    return { 
      id: response.data.data, 
      ...data,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }
  } catch (error) {
    throw error
  }
}

// 更新流程图 Nexus
export const updateWorkflow = async (id: string, data: any): Promise<any> => {
  try {
    const response = await apiClient.put<ApiResponse<any>>(`/workflow/update/${id}`, data)
    return response.data.data
  } catch (error) {
    throw error
  }
}

// 删除流程图 Nexus
export const deleteWorkflow = async (id: string): Promise<void> => {
  try {
    await apiClient.delete<ApiResponse<any>>(`/workflow/delete/${id}`)
  } catch (error) {
    throw error
  }
}

export const getWorkflowNodeList = async (): Promise<NodeTypeDefinition[]> => {
  try {
    const response = await apiClient.get<ApiResponse<NodeTypeDefinition[]>>('/workflow/node/list')
    return response.data.data
  } catch (error) {
    console.error("get workflow node list failed", error)
    return []
  }
}

// 获取默认工作流画布配置
export const getDefaultWorkflowCanvas = async (): Promise<CanvasResponse> => {
  try {
    const response = await apiClient.get<ApiResponse<CanvasResponse>>('/workflow/canvas/init')
    return response.data.data
  } catch (error) {
    console.error("get default workflow canvas failed", error)
    return { nodes: [], edges: [] }
  }
}

// 获取流程图列表的 Nexus
export const getWorkflows = async (): Promise<WorkflowResponse[]> => {
  try {
    const response = await apiClient.get<ApiResponse<WorkflowResponse[]>>('/workflow/list')
    return response.data.data
  } catch (error) {
    console.error("get workflow list failed", error)
    return [] 
  }
}

import { workflow_graph } from '../utils/workflowGraph.js'

const MESSAGE_TARGET = '*'
const RENDER_MESSAGE_TYPE = 'FASTFLOW_RENDER'
const RENDER_RESULT_TYPE = 'FASTFLOW_RENDER_RESULT'
const EXPORT_MESSAGE_TYPE = 'FASTFLOW_EXPORT'
const EXPORT_RESULT_TYPE = 'FASTFLOW_EXPORT_RESULT'
const EXPORT_ERROR_MESSAGE = '未能读取当前编排数据'

// 监听来自 Overlay Script 的消息
window.addEventListener('message', function handleMessage(event) {
  // 安全校验：只接受来自我们插件的消息
  if (event.source !== window || !event.data) {
    return
  }

  if (event.data.type === RENDER_MESSAGE_TYPE) {
    const { nodes, edges } = event.data.payload
    console.log('[FastFlow] 收到渲染请求:', nodes.length, '个节点')

    const success = workflow_graph.import(nodes, edges)
    
    // 回复插件：渲染结果
    window.postMessage({ 
      type: RENDER_RESULT_TYPE,
      success 
    }, MESSAGE_TARGET)
    return
  }

  if (event.data.type === EXPORT_MESSAGE_TYPE) {
    workflow_graph
      .export()
      .then((payload) => {
        window.postMessage({ 
          type: EXPORT_RESULT_TYPE,
          success: true,
          payload
        }, MESSAGE_TARGET)
      })
      .catch((err) => {
        window.postMessage({ 
          type: EXPORT_RESULT_TYPE,
          success: false,
          message: err?.message || EXPORT_ERROR_MESSAGE
        }, MESSAGE_TARGET)
      })
  }
})

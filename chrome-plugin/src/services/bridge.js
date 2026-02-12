import { Logger } from '@/utils/logger.js'

const MESSAGE_TARGET = '*'
const RENDER_MESSAGE_TYPE = 'FASTFLOW_RENDER'
const RENDER_RESULT_TYPE = 'FASTFLOW_RENDER_RESULT'
const EXPORT_MESSAGE_TYPE = 'FASTFLOW_EXPORT'
const EXPORT_RESULT_TYPE = 'FASTFLOW_EXPORT_RESULT'
const EXPORT_TIMEOUT_MS = 3000

function injectScript() {
  Logger.step(1, '开始注入通信脚本 (inject.js)...')
  const script = document.createElement('script')
  // Use absolute path from extension root
  script.src = chrome.runtime.getURL('src/inject/index.js')
  script.onload = () => {
    Logger.info('通信脚本注入完成')
    script.remove()
  }
  (document.head || document.documentElement).appendChild(script)
}

function sendRenderRequest(graphData, onSuccess, onFail) {
  Logger.info('⚡️ 正在尝试无感注入新画布...')
  
  // 发送消息给 inject.js
  window.postMessage({
    type: RENDER_MESSAGE_TYPE,
    payload: graphData
  }, MESSAGE_TARGET)

  // 监听结果
  const resultListener = (event) => {
    if (event.data && event.data.type === RENDER_RESULT_TYPE) {
      if (event.data.success) {
        onSuccess()
      } else {
        onFail()
      }
      window.removeEventListener('message', resultListener)
    }
  }
  window.addEventListener('message', resultListener)
}

function getCurrentGraph() {
  return new Promise((resolve, reject) => {
    // 发送消息给 inject.js 请求当前图
    window.postMessage({
      type: EXPORT_MESSAGE_TYPE
    }, MESSAGE_TARGET)

    const timeout = setTimeout(() => {
      window.removeEventListener('message', resultListener)
      reject(new Error('获取当前编排超时'))
    }, EXPORT_TIMEOUT_MS)

    const resultListener = (event) => {
      if (!event.data || event.data.type !== EXPORT_RESULT_TYPE) return
      clearTimeout(timeout)
      window.removeEventListener('message', resultListener)
      if (event.data.success) {
        resolve(event.data.payload)
      } else {
        reject(new Error(event.data.message || '获取当前编排失败'))
      }
    }

    window.addEventListener('message', resultListener)
  })
}

export const Bridge = {
  injectScript,
  sendRenderRequest,
  getCurrentGraph
}

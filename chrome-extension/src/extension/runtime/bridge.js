import { Logger } from '@/shared/utils/logger.js'
import { injectScript as injectUnlistedScript } from 'wxt/utils/inject-script'

const MESSAGE_TARGET = '*'
const RENDER_MESSAGE_TYPE = 'FASTFLOW_RENDER'
const RENDER_RESULT_TYPE = 'FASTFLOW_RENDER_RESULT'
const EXPORT_MESSAGE_TYPE = 'FASTFLOW_EXPORT'
const EXPORT_RESULT_TYPE = 'FASTFLOW_EXPORT_RESULT'
const EXPORT_META_MESSAGE_TYPE = 'FASTFLOW_EXPORT_META'
const EXPORT_META_RESULT_TYPE = 'FASTFLOW_EXPORT_META_RESULT'
const EXPORT_TIMEOUT_MS = 3000
const INJECT_SCRIPT_PATH = 'inject.js'
const INJECT_TIMEOUT_MS = 2500

let injectReady = false
let injectInFlightPromise = null

function ensureInjectScript() {
  if (injectReady) return Promise.resolve()
  if (injectInFlightPromise) return injectInFlightPromise

  Logger.step(1, '开始注入通信脚本 (inject.js)...')
  injectInFlightPromise = new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('注入通信脚本超时，请刷新页面后重试'))
    }, INJECT_TIMEOUT_MS)

    const cleanup = () => {
      clearTimeout(timer)
      injectInFlightPromise = null
    }

    injectUnlistedScript(INJECT_SCRIPT_PATH)
      .then(() => {
        injectReady = true
        Logger.info('通信脚本注入完成')
        cleanup()
        resolve()
      })
      .catch((error) => {
        injectReady = false
        cleanup()
        reject(new Error(`通信脚本不可用（通常是扩展目录不是最新构建产物）：${error.message}`))
      })
  })

  return injectInFlightPromise
}

function sendRenderRequest(graphData, onSuccess, onFail) {
  Logger.info('⚡️ 正在尝试无感注入新画布...')

  ensureInjectScript()
    .then(() => {
      // 发送消息给 inject.js
      window.postMessage(
        {
          type: RENDER_MESSAGE_TYPE,
          payload: graphData
        },
        MESSAGE_TARGET
      )

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
    })
    .catch((error) => {
      Logger.error(error.message)
      onFail()
    })
}

function exportWorkflowGraph() {
  return ensureInjectScript().then(
    () =>
      new Promise((resolve, reject) => {
        // 发送消息给 inject.js，静默触发页面导出并回传导出原文。
        window.postMessage(
          {
            type: EXPORT_MESSAGE_TYPE
          },
          MESSAGE_TARGET
        )

        const timeout = setTimeout(() => {
          window.removeEventListener('message', resultListener)
          reject(new Error('导出当前编排超时'))
        }, EXPORT_TIMEOUT_MS)

        const resultListener = (event) => {
          if (!event.data || event.data.type !== EXPORT_RESULT_TYPE) return
          clearTimeout(timeout)
          window.removeEventListener('message', resultListener)
          if (event.data.success) {
            resolve(event.data.payload)
          } else {
            reject(new Error(event.data.message || '导出当前编排失败'))
          }
        }

        window.addEventListener('message', resultListener)
      })
  )
}

function exportWorkflowMeta() {
  return ensureInjectScript().then(
    () =>
      new Promise((resolve, reject) => {
        window.postMessage(
          {
            type: EXPORT_META_MESSAGE_TYPE
          },
          MESSAGE_TARGET
        )

        const timeout = setTimeout(() => {
          window.removeEventListener('message', resultListener)
          reject(new Error('读取当前工作流名称和描述超时'))
        }, EXPORT_TIMEOUT_MS)

        const resultListener = (event) => {
          if (!event.data || event.data.type !== EXPORT_META_RESULT_TYPE) return
          clearTimeout(timeout)
          window.removeEventListener('message', resultListener)
          if (event.data.success) {
            resolve(event.data.payload || null)
          } else {
            reject(new Error(event.data.message || '读取当前工作流名称和描述失败'))
          }
        }

        window.addEventListener('message', resultListener)
      })
  )
}

export const Bridge = {
  injectScript: ensureInjectScript,
  sendRenderRequest,
  exportWorkflowGraph,
  exportWorkflowMeta
}

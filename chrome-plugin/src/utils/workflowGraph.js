const FLOW_CONTAINER_SELECTOR = '.react-flow'
const FIBER_KEY_PREFIX = '__reactFiber$'
const PASTE_EVENT_TYPE = 'paste'
const PASTE_MIME_TYPE = 'text/plain'
const EXPORT_TIMEOUT_MS = 2000
const REACT_PROPS_PREFIX = '__reactProps$'
const MENU_EXPORT_KEY = 'dataExport'

function importWorkflowGraph(nodes, edges) {
  const flowContainer = document.querySelector(FLOW_CONTAINER_SELECTOR)
  if (!flowContainer) {
    console.error('[FastFlow] 未找到 .react-flow 容器')
    return false
  }

  const key = Object.keys(flowContainer).find((candidateKey) => candidateKey.startsWith(FIBER_KEY_PREFIX))
  if (!key) {
    console.error('[FastFlow] 无法获取 React Fiber 实例')
    return false
  }

  try {
    const clipboardData = new DataTransfer()
    clipboardData.setData(PASTE_MIME_TYPE, JSON.stringify({ nodes, edges }))
    const pasteEvent = new ClipboardEvent(PASTE_EVENT_TYPE, {
      bubbles: true,
      cancelable: true,
      clipboardData
    })
    flowContainer.dispatchEvent(pasteEvent)
    return true
  } catch (error) {
    console.error('[FastFlow] 注入失败:', error)
    return false
  }
}

async function exportWorkflowGraph(options = {}) {
  const timeout = Number(options.timeout) > 0 ? Number(options.timeout) : EXPORT_TIMEOUT_MS
  const capture = createClipboardCapture(timeout)

  try {
    triggerExportByToolbarMenu()
  } catch (error) {
    capture.cancel()
    throw error
  }

  return capture.wait()
}

function triggerExportByToolbarMenu() {
  if (!document.querySelector(FLOW_CONTAINER_SELECTOR)) {
    throw new Error('当前 frame 未检测到编排画布（react-flow），无法导出')
  }

  const triggerButton = findTopToolbarDropdownTrigger()
  if (!triggerButton) {
    throw new Error('未找到顶部导入/导出菜单按钮')
  }

  const container = triggerButton.parentElement || triggerButton
  const containerProps = getReactProps(container) || getReactProps(triggerButton)
  if (!containerProps) {
    throw new Error('未获取到顶部菜单容器的 React props')
  }

  const menuOnClick = findMenuOnClick(containerProps)
  if (typeof menuOnClick !== 'function') {
    throw new Error('未找到导出菜单 onClick')
  }

  const ok = invokeMenuHandler(menuOnClick)
  if (!ok) {
    throw new Error('调用导出菜单 onClick 失败')
  }
}

function findTopToolbarDropdownTrigger() {
  const candidates = Array.from(document.querySelectorAll('button.ant-dropdown-trigger'))
  const topCandidates = candidates.filter((btn) => {
    const rect = btn.getBoundingClientRect()
    return rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.top < 80
  })

  if (topCandidates.length === 0) return null

  topCandidates.sort((a, b) => b.getBoundingClientRect().left - a.getBoundingClientRect().left)
  return topCandidates[0]
}

function findMenuOnClick(rootProps) {
  const seen = new WeakSet()

  function walk(value, depth) {
    if (!value || typeof value !== 'object') return null
    if (seen.has(value) || depth > 12) return null
    seen.add(value)

    // 目标结构：{ menu: { items:[{key:'dataExport'}], onClick: fn } }
    if (value.menu && typeof value.menu === 'object') {
      const items = value.menu.items
      if (Array.isArray(items) && items.some((it) => it && it.key === MENU_EXPORT_KEY)) {
        const onClick = value.menu.onClick
        if (typeof onClick === 'function') return onClick
      }
    }

    for (const child of Object.values(value)) {
      if (child && typeof child === 'object') {
        const hit = walk(child, depth + 1)
        if (hit) return hit
      }
    }

    return null
  }

  return walk(rootProps, 0)
}

function invokeMenuHandler(handler) {
  try {
    const domEvent = new MouseEvent('click', { bubbles: true, cancelable: true })
    handler({
      key: MENU_EXPORT_KEY,
      keyPath: [MENU_EXPORT_KEY],
      domEvent,
      preventDefault: () => {},
      stopPropagation: () => {}
    })
    return true
  } catch (error) {
    console.error('[FastFlow] 调用导出菜单 handler 失败:', error)
    return false
  }
}

function getReactProps(element) {
  if (!element) return null
  const key = Object.keys(element).find((candidateKey) => candidateKey.startsWith(REACT_PROPS_PREFIX))
  if (!key) return null
  return element[key]
}

function createClipboardCapture(timeoutMs) {
  let done = false
  let timerId = null

  const originalExecCommand = document.execCommand
  const restoreClipboardWriteText = overrideClipboardWriteText((text) => {
    if (typeof text === 'string' && text) {
      finalize(text)
    }
  })

  let resolvePromise
  let rejectPromise

  const restore = () => {
    if (typeof restoreClipboardWriteText === 'function') restoreClipboardWriteText()
    if (typeof originalExecCommand === 'function') {
      document.execCommand = originalExecCommand
    }
  }

  const finalize = (text) => {
    if (done) return
    done = true
    if (timerId) clearTimeout(timerId)
    restore()
    resolvePromise(text)
  }

  const fail = (error) => {
    if (done) return
    done = true
    if (timerId) clearTimeout(timerId)
    restore()
    rejectPromise(error)
  }

  const wait = new Promise((resolve, reject) => {
    resolvePromise = resolve
    rejectPromise = reject
  })

  if (typeof originalExecCommand === 'function') {
    document.execCommand = function patchedExecCommand(command, ...args) {
      if (String(command).toLowerCase() === 'copy') {
        const selectedText = readSelectedText()
        if (selectedText) finalize(selectedText)
      }
      return originalExecCommand.call(document, command, ...args)
    }
  }

  timerId = setTimeout(() => {
    fail(new Error('导出超时'))
  }, timeoutMs)

  return {
    wait: () => wait,
    cancel: () => {
      if (done) return
      done = true
      if (timerId) clearTimeout(timerId)
      restore()
    }
  }
}

function overrideClipboardWriteText(onCaptured) {
  const clipboard = navigator.clipboard
  if (!clipboard || typeof clipboard.writeText !== 'function') return null

  const originalWriteText = clipboard.writeText
  const patchedWriteText = async function patchedWriteText(text) {
    onCaptured(text)
    return originalWriteText.call(clipboard, text)
  }

  try {
    clipboard.writeText = patchedWriteText
    return () => {
      clipboard.writeText = originalWriteText
    }
  } catch (_) {
    return null
  }
}

function readSelectedText() {
  const activeElement = document.activeElement
  if (activeElement && (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT')) {
    const value = activeElement.value || ''
    if (typeof activeElement.selectionStart === 'number' && typeof activeElement.selectionEnd === 'number') {
      return value.slice(activeElement.selectionStart, activeElement.selectionEnd)
    }
    return value
  }

  const selection = document.getSelection && document.getSelection()
  return selection ? selection.toString() : ''
}

export const workflow_graph = {
  import: importWorkflowGraph,
  export: exportWorkflowGraph
}

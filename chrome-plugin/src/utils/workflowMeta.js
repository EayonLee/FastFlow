function getText(el) {
  if (!el) return ''
  return (el.textContent || '').replace(/\s+/g, ' ').trim()
}

// 过滤掉明显不是“工作流描述”的文本
function isInvalidDescription(text, workflowName) {
  if (!text) return true
  if (text === workflowName) return true
  if (text.includes('已自动保存')) return true
  if (text.includes('调 试') || text.includes('发布')) return true
  if (text.includes('基础组件') || text.includes('安全组件') || text.includes('安全工作流')) return true
  return false
}

// 把页面左上区域的“可见短文本元素”收集出来
function collectTopLeftTextNodes() {
  const nodes = Array.from(document.querySelectorAll('body *'))
  const items = []

  for (const el of nodes) {
    const text = getText(el)
    if (!text) continue
    if (text.length > 120) continue

    const rect = el.getBoundingClientRect()
    if (rect.width <= 0 || rect.height <= 0) continue
    if (rect.top < 0 || rect.top > 120) continue
    if (rect.left < 0 || rect.left > 800) continue

    // 排除容器文本（只保留“叶子文本”）
    const childHasSameText = Array.from(el.children).some((child) => getText(child) === text)
    if (childHasSameText) continue

    items.push({ el, text, top: rect.top, left: rect.left })
  }

  return items
}

// 描述通常在“名称正下方、同一列附近”
function findDescriptionNearName(workflowName) {
  const items = collectTopLeftTextNodes()
  const nameItem = items.find((item) => item.text === workflowName)
  if (!nameItem) return ''

  const candidates = items
    .filter((item) => !isInvalidDescription(item.text, workflowName))
    .filter((item) => item.top > nameItem.top && item.top - nameItem.top < 50)
    .filter((item) => Math.abs(item.left - nameItem.left) < 40)
    .sort((a, b) => a.top - b.top)

  return candidates[0]?.text || ''
}

function exportWorkflowMeta() {
  // 当前详情页 title 就是工作流名称（例如：本脑辅助运营）
  const workflowName = getText(document.querySelector('title'))
  // 描述从“名称下方同列文本”提取（例如：这是本脑辅助运营）
  const workflowDescription = findDescriptionNearName(workflowName)

  if (!workflowName && !workflowDescription) return null
  return {
    workflow_name: workflowName || '',
    workflow_description: workflowDescription || ''
  }
}

export const workflow_meta = {
  export: exportWorkflowMeta
}

/**
 * 内联协议文本解析器。
 *
 * 支持：
 * - selected_skill(<skill_name>)
 * - selected_node(<node_id>)
 */

const SKILL_NAME_PATTERN = '[a-z0-9-]+'
const NODE_ID_PATTERN = '[^\\)\\s]+'
const INLINE_PROTOCOL_REGEX = new RegExp(
  `selected_skill\\((${SKILL_NAME_PATTERN})\\)|selected_node\\((${NODE_ID_PATTERN})\\)`,
  'g',
)

export function splitProtocolText(rawText) {
  const input = String(rawText || '')
  const segments = []
  let lastIndex = 0
  let match

  // 线性扫描并按原顺序切分，保证“文本 + 多协议标签”顺序稳定。
  INLINE_PROTOCOL_REGEX.lastIndex = 0
  while ((match = INLINE_PROTOCOL_REGEX.exec(input)) !== null) {
    const [fullText, skillName, nodeId] = match
    const start = match.index
    const end = start + fullText.length

    if (start > lastIndex) {
      segments.push({ type: 'text', text: input.slice(lastIndex, start) })
    }

    if (skillName) {
      segments.push({ type: 'skill', name: skillName })
    } else if (nodeId) {
      segments.push({ type: 'node', node_id: nodeId })
    }

    lastIndex = end
  }

  if (lastIndex < input.length) {
    segments.push({ type: 'text', text: input.slice(lastIndex) })
  }
  if (segments.length === 0) {
    segments.push({ type: 'text', text: input })
  }

  return segments
}

// 兼容旧调用点命名，后续逐步移除。
export const splitSkillProtocolText = splitProtocolText

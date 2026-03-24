import { mergeAttributes, Node } from '@tiptap/core'

/**
 * 协议层共用工具：
 * - 统一字符串归一化
 * - trigger 正则构造
 * - TipTap 协议 token 节点工厂
 */
export function normalizeString(value) {
  return String(value || '').trim()
}

export function toShortId(value, length = 8) {
  const normalized = normalizeString(value)
  if (!normalized) return ''
  if (normalized.length <= length) return normalized
  return normalized.slice(-length)
}

function escapeRegexText(text) {
  return String(text || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function createTriggerRegex(triggerChar, queryPattern, flags = 'i') {
  const escapedTrigger = escapeRegexText(triggerChar)
  return new RegExp(`(^|\\s)${escapedTrigger}(${queryPattern})$`, flags)
}

/**
 * 创建一个“协议 token”节点：
 * - 输入区以标签展示
 * - 序列化仅用于编辑器内部纯文本表示，不承担网络协议职责
 */
export function createProtocolTokenNode(config) {
  const {
    nodeName,
    dataAttr,
    cssClass,
    attrs,
    getLabel,
    serializeText,
  } = config

  return Node.create({
    name: nodeName,
    group: 'inline',
    inline: true,
    atom: true,
    selectable: false,
    addAttributes() {
      return attrs
    },
    parseHTML() {
      return [{ tag: `span[${dataAttr}]` }]
    },
    renderHTML({ HTMLAttributes }) {
      return [
        'span',
        mergeAttributes(HTMLAttributes, {
          [dataAttr]: '1',
          class: cssClass,
        }),
        getLabel(HTMLAttributes),
      ]
    },
    renderText({ node }) {
      return serializeText(node.attrs)
    },
  })
}

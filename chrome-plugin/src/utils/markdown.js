import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/common'
import { getCachedMermaidSvg, hashMermaidSource, isSupportedMermaidSource } from '@/utils/mermaid.js'

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: true,
  highlight(str, lang) {
    const language = String(lang || '').trim().toLowerCase()
    if (language && hljs.getLanguage(language)) {
      const highlighted = hljs.highlight(str, { language, ignoreIllegals: true }).value
      return `<pre class="msg-code-block"><code class="hljs language-${language}">${highlighted}</code></pre>`
    }

    const highlighted = hljs.highlightAuto(str).value
    return `<pre class="msg-code-block"><code class="hljs">${highlighted}</code></pre>`
  }
})

// Mermaid 目前需要前端渲染：这里先把 ```mermaid``` 代码块标记成可识别的容器，
// 后续由 DOM 后处理（utils/mermaid.js）渲染为 SVG。
const defaultFenceRenderer =
  md.renderer.rules.fence ||
  function fence(tokens, idx, options, env, self) {
    return self.renderToken(tokens, idx, options)
  }
md.renderer.rules.fence = function fence(tokens, idx, options, env, self) {
  const token = tokens[idx]
  const info = String(token.info || '').trim()
  const lang = info.split(/\s+/g)[0].toLowerCase()

  if (lang === 'mermaid') {
    const source = String(token.content || '')
    const normalizedSource = source.trim()
    const key = hashMermaidSource(normalizedSource)

    // 已渲染过的图：直接输出缓存的 SVG，避免流式更新时 DOM 重绘导致回退为代码块。
    const cachedSvg = getCachedMermaidSvg(normalizedSource)
    if (cachedSvg) {
      return `<div class="msg-mermaid" data-rendered="1" data-key="${escapeHtml(key)}">${cachedSvg}</div>`
    }

    const escapedSource = escapeHtml(source)
    const supported = isSupportedMermaidSource(normalizedSource)
    const hint = supported ? '' : '<div class="msg-mermaid-error">仅支持渲染 graph/flowchart 流程图。</div>'
    return [
      `<div class="msg-mermaid" data-rendered="0" data-key="${escapeHtml(key)}">`,
      `<pre class="msg-code-block"><code class="language-mermaid">${escapedSource}</code></pre>`,
      hint,
      '</div>'
    ].join('')
  }

  return defaultFenceRenderer(tokens, idx, options, env, self)
}

// 给表格添加容器与样式类，便于横向滚动与统一 UI。
md.renderer.rules.table_open = () => '<div class="msg-table-wrap"><table class="msg-table">'
md.renderer.rules.table_close = () => '</table></div>'

// 外链默认新窗口打开，避免打断聊天上下文。
const defaultLinkOpen =
  md.renderer.rules.link_open ||
  function linkOpen(tokens, idx, options, env, self) {
    return self.renderToken(tokens, idx, options)
  }
md.renderer.rules.link_open = function linkOpen(tokens, idx, options, env, self) {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer nofollow')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

function isPotentialTableRow(line) {
  const trimmed = String(line || '').trim()
  if (!trimmed.includes('|')) return false
  const cells = trimmed.replace(/^\|/, '').replace(/\|$/, '').split('|')
  return cells.length >= 2
}

function isTableDelimiter(line) {
  const trimmed = String(line || '').trim()
  const normalized = trimmed.replace(/^\|/, '').replace(/\|$/, '')
  const cells = normalized.split('|').map((cell) => cell.trim())
  if (cells.length < 2) return false
  return cells.every((cell) => /^:?-{3,}:?$/.test(cell))
}

function findNextNonEmptyIndex(lines, start) {
  for (let i = start; i < lines.length; i += 1) {
    if (String(lines[i] || '').trim()) return i
  }
  return -1
}

/**
 * 归一化“松散表格”：
 * 允许模型在表头/分隔/数据行之间插入空行，渲染前压缩为空连续表格语法。
 */
function normalizeLooseTables(markdown) {
  const lines = String(markdown || '').split('\n')
  const out = []

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    if (!isPotentialTableRow(line)) {
      out.push(line)
      continue
    }

    const delimiterIdx = findNextNonEmptyIndex(lines, i + 1)
    if (delimiterIdx === -1 || !isTableDelimiter(lines[delimiterIdx])) {
      out.push(line)
      continue
    }

    const tableLines = [line, lines[delimiterIdx]]
    let j = delimiterIdx + 1
    while (j < lines.length) {
      const current = lines[j]
      const trimmed = String(current || '').trim()

      if (!trimmed) {
        const nextIdx = findNextNonEmptyIndex(lines, j + 1)
        if (nextIdx !== -1 && isPotentialTableRow(lines[nextIdx]) && !isTableDelimiter(lines[nextIdx])) {
          j += 1
          continue
        }
        break
      }

      if (!isPotentialTableRow(current) || isTableDelimiter(current)) break
      tableLines.push(current)
      j += 1
    }

    out.push(...tableLines)
    i = j - 1
  }

  return out.join('\n')
}

/**
 * 将 Markdown 文本渲染为安全 HTML。
 * @param {string} markdown
 * @returns {string}
 */
export function renderMarkdown(markdown) {
  return md.render(normalizeLooseTables(markdown))
}

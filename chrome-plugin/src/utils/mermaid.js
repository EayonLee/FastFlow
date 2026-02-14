/**
 * Mermaid 渲染工具：
 * - Markdown 渲染阶段会把 ```mermaid``` 代码块输出为 <div class="msg-mermaid"> 容器。
 * - 本模块在 DOM 渲染后扫描这些容器，并按需动态加载 mermaid，将其渲染为 SVG。
 *
 * 设计目标：
 * - 轻量：仅当页面上出现 mermaid 容器时才加载依赖（Vite 会拆分为独立 chunk）。
 * - 安全：使用 strict 安全级别；渲染失败则保留原始代码块展示。
 */

// Mermaid ESM 入口会做较多懒加载，这里用缓存 + 延迟加载来保证：
// 1) 没有 mermaid 块就不加载依赖
// 2) 同一段图的渲染结果可复用，避免流式更新时反复渲染/反复报错
let mermaidApiPromise = null

// source_hash -> svg 字符串
const _svgCache = new Map()
// source_hash -> Promise<string>（防止并发重复渲染同一段）
const _svgPromiseCache = new Map()

async function loadMermaid() {
  if (!mermaidApiPromise) {
    mermaidApiPromise = import('mermaid').then((mod) => mod.default || mod)
  }
  return mermaidApiPromise
}

/**
 * 将 Mermaid source 归一化为 hash key（用于缓存）。
 * 说明：这里用轻量的 FNV-1a 32-bit 哈希，避免引入额外依赖。
 * @param {string} source
 * @returns {string}
 */
export function hashMermaidSource(source) {
  const str = String(source || '')
  let hash = 0x811c9dc5
  for (let i = 0; i < str.length; i += 1) {
    hash ^= str.charCodeAt(i)
    // eslint-disable-next-line no-bitwise
    hash = (hash * 0x01000193) >>> 0
  }
  return `mmd-${hash.toString(16)}`
}

/**
 * 判断当前 Mermaid source 是否属于我们允许渲染的子集。
 * 目的：
 * - 避免渲染饼图/时序图等导致额外模块加载与错误
 * - 与后端提示词保持一致：只画最基础的 graph TB/TD
 * @param {string} source
 * @returns {boolean}
 */
export function isSupportedMermaidSource(source) {
  const lines = String(source || '')
    .split('\n')
    .map((l) => String(l || '').trim())
    .filter(Boolean)
  if (lines.length === 0) return false
  const first = lines[0].toLowerCase()
  // 只允许最常用的 flowchart/graph 入口，其他全部视为不支持（仍以代码块展示）
  return first.startsWith('graph ') || first === 'graph' || first.startsWith('flowchart ')
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function createSvgId() {
  return `mermaid-svg-${Math.random().toString(16).slice(2)}-${Date.now()}`
}

/**
 * 读取缓存的 SVG（如果存在）。
 * @param {string} source
 * @returns {string|null}
 */
export function getCachedMermaidSvg(source) {
  const key = hashMermaidSource(source)
  return _svgCache.get(key) || null
}

async function renderMermaidSourceToSvg(source) {
  const key = hashMermaidSource(source)
  const cached = _svgCache.get(key)
  if (cached) return cached

  const inflight = _svgPromiseCache.get(key)
  if (inflight) return inflight

  const p = (async () => {
    const mermaid = await loadMermaid()
    // 只初始化一次即可；重复初始化可能导致配置被覆盖或性能浪费。
    if (!renderMermaidInElement.__inited) {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict'
      })
      renderMermaidInElement.__inited = true
    }

    const { svg } = await mermaid.render(createSvgId(), source)
    _svgCache.set(key, svg)
    return svg
  })()

  _svgPromiseCache.set(key, p)
  try {
    return await p
  } finally {
    _svgPromiseCache.delete(key)
  }
}

/**
 * 在指定根节点内渲染所有未渲染的 Mermaid 图。
 * @param {HTMLElement} rootEl
 */
export async function renderMermaidInElement(rootEl) {
  if (!rootEl || typeof rootEl.querySelectorAll !== 'function') return

  const blocks = Array.from(rootEl.querySelectorAll('.msg-mermaid[data-rendered="0"]'))
  if (blocks.length === 0) return

  for (const block of blocks) {
    try {
      const codeEl = block.querySelector('code.language-mermaid')
      const source = codeEl ? String(codeEl.textContent || '').trim() : ''
      if (!source) {
        block.setAttribute('data-rendered', 'empty')
        continue
      }

      // 只渲染我们允许的 Mermaid 子集，其余保持代码块展示（避免额外模块加载/错误）。
      if (!isSupportedMermaidSource(source)) {
        block.setAttribute('data-rendered', 'unsupported')
        block.insertAdjacentHTML('beforeend', '<div class="msg-mermaid-error">仅支持渲染 graph/flowchart 流程图。</div>')
        continue
      }

      const svg = await renderMermaidSourceToSvg(source)
      block.innerHTML = svg
      block.setAttribute('data-rendered', '1')
    } catch (e) {
      // 渲染失败：保留原始 code block，同时给一个轻提示，便于用户定位问题。
      block.setAttribute('data-rendered', 'error')
      const msg = escapeHtml(e && e.message ? e.message : String(e))
      block.insertAdjacentHTML('beforeend', `<div class="msg-mermaid-error">Mermaid 渲染失败：${msg}</div>`)
    }
  }
}

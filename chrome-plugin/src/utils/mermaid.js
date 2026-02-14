/**
 * Mermaid 渲染工具：
 * - Markdown 渲染阶段会把 ```mermaid``` 代码块输出为 <div class="msg-mermaid"> 容器。
 * - 本模块在 DOM 渲染后扫描这些容器，并按需动态加载 mermaid，将其渲染为 SVG。
 *
 * 设计目标：
 * - 轻量：仅当页面上出现 mermaid 容器时才加载依赖（Vite 会拆分为独立 chunk）。
 * - 安全：使用 strict 安全级别；渲染失败则保留原始代码块展示。
 */

import { themeManager } from '@/utils/themeManager.js'

// Mermaid ESM 入口会做较多懒加载，这里用缓存 + 延迟加载来保证：
// 1) 没有 mermaid 块就不加载依赖
// 2) 同一段图的渲染结果可复用，避免流式更新时反复渲染/反复报错
let mermaidApiPromise = null

// source_hash -> svg 字符串
const _svgCache = new Map()
// source_hash -> Promise<string>（防止并发重复渲染同一段）
const _svgPromiseCache = new Map()
// key -> source（用于“复制 Mermaid 语句”等功能；避免渲染后丢失原始代码）
const _sourceCache = new Map()

// Mermaid 渲染需要真实 DOM 来测量文本/布局（尤其是 htmlLabels/foreignObject）。
// 我们的聊天 UI 挂载在 Shadow DOM 内，直接在 Shadow DOM 容器上渲染时，
// Mermaid 内部有概率拿不到期望的节点（出现 div.node() 为 null，进而 getBoundingClientRect 报错）。
// 因此统一使用“主文档的离屏渲染沙箱”进行渲染，再把 SVG 字符串注入 Shadow DOM。
let _renderSandboxEl = null

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
 * 获取当前“已解析”的主题（只返回 light/dark）。
 * 说明：Content Script 环境下主题挂在 Shadow Host 上；ThemeManager 已负责同步与解析 system。
 * @returns {"light"|"dark"}
 */
function getResolvedTheme() {
  try {
    const resolved = themeManager?.resolveTheme?.()
    return resolved === 'light' ? 'light' : 'dark'
  } catch (_) {
    return 'dark'
  }
}

/**
 * SVG 缓存需要“主题维度”参与：
 * - Mermaid 不支持 themeVariables 使用 CSS var()（会报 Unsupported color format）
 * - 因此切主题时必须重渲染，而缓存按主题分离可保证“切回去秒切”且不串色
 * @param {string} source
 * @returns {string}
 */
function getSvgCacheKey(source) {
  const theme = getResolvedTheme()
  return hashMermaidSource(`${theme}::${String(source || '')}`)
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

function getOrCreateRenderSandbox() {
  if (_renderSandboxEl && document.contains(_renderSandboxEl)) {
    return _renderSandboxEl
  }

  const el = document.createElement('div')
  el.id = 'fastflow-mermaid-render-sandbox'
  // 避免翻译类插件对离屏 DOM 做文本替换，影响 Mermaid 内部的测量与渲染逻辑。
  el.className = 'notranslate'
  el.setAttribute('translate', 'no')
  // 离屏但可测量：不要 display:none，否则 getBBox/getBoundingClientRect 可能为 0 或异常。
  Object.assign(el.style, {
    position: 'fixed',
    left: '-10000px',
    top: '-10000px',
    // Mermaid 渲染过程会依赖容器尺寸做布局计算（不同图类型内部算法不同）。
    // 这里给一个足够大的“画布”，避免出现 0 尺寸导致的 Infinity/-Infinity 等异常。
    width: '4096px',
    height: '4096px',
    overflow: 'hidden',
    visibility: 'hidden',
    pointerEvents: 'none'
  })
  // 关键：必须挂在 body 下。
  // Mermaid 的不少图类型渲染器内部会直接 select('body') 来取 svg 容器（例如 timeline 等），
  // 如果我们把沙箱挂到 <html>（documentElement）而不是 <body>，这些渲染器会拿不到 svg，
  // 进而出现 `...node() === null`，导致 getComputedTextLength/getBoundingClientRect 等空指针错误。
  const parent = document.body || document.documentElement
  parent.appendChild(el)
  _renderSandboxEl = el
  return el
}

/**
 * 读取缓存的 SVG（如果存在）。
 * @param {string} source
 * @returns {string|null}
 */
export function getCachedMermaidSvg(source) {
  const key = getSvgCacheKey(source)
  return _svgCache.get(key) || null
}

/**
 * 记住 Mermaid 原始语句（用于复制）。
 * @param {string} key
 * @param {string} source
 */
export function rememberMermaidSource(key, source) {
  const k = String(key || '').trim()
  const s = String(source || '')
  if (!k || !s) return
  // 不覆盖已有值：避免同 key 因 whitespace 差异被反复写入
  if (!_sourceCache.has(k)) _sourceCache.set(k, s)
}

/**
 * 通过 data-key 获取 Mermaid 原始语句。
 * @param {string} key
 * @returns {string|null}
 */
export function getMermaidSourceByKey(key) {
  const k = String(key || '').trim()
  if (!k) return null
  return _sourceCache.get(k) || null
}

async function renderMermaidSourceToSvg(source) {
  const key = getSvgCacheKey(source)
  const cached = _svgCache.get(key)
  if (cached) return cached

  const inflight = _svgPromiseCache.get(key)
  if (inflight) return inflight

  const p = (async () => {
    const mermaid = await loadMermaid()
    // Mermaid 不支持在 themeVariables 里传 var(--xxx)，因此只能按主题重渲染。
    // 为了避免重复初始化造成全局配置抖动，这里仅在“首次”或“主题变化”时 initialize。
    const resolvedTheme = getResolvedTheme()
    const desiredMermaidTheme = resolvedTheme === 'dark' ? 'dark' : 'default'

    if (!renderMermaidInElement.__inited || renderMermaidInElement.__theme !== desiredMermaidTheme) {
      mermaid.initialize({
        startOnLoad: false,
        theme: desiredMermaidTheme,
        // 关键：必须输出“内联 SVG”，否则会得到 sandbox iframe 包装，
        // 进而无法在消息区域中做点击放大与 svg-pan-zoom 交互。
        //
        // 我们通过：
        // 1) 渲染沙箱挂在 document.body 下（见 getOrCreateRenderSandbox）
        // 2) 关闭 htmlLabels
        // 来保证 strict 模式下的稳定性。
        securityLevel: 'strict',
        // 关键：关闭 htmlLabels，避免 Mermaid 走 foreignObject + DOM 测量路径。
        // 在浏览器插件（Shadow DOM + 各类页面/插件干扰）环境下，htmlLabels 很容易触发
        // “div.node() 为空 -> getBoundingClientRect 报错”一类问题。
        htmlLabels: false,
        // 对 flowchart 单独再显式关一次，防止图类型配置覆盖全局开关。
        flowchart: { htmlLabels: false }
      })
      renderMermaidInElement.__inited = true
      renderMermaidInElement.__theme = desiredMermaidTheme
    }

    const sandbox = getOrCreateRenderSandbox()

    // Mermaid 官方渲染 API：使用主文档离屏容器进行渲染，避免 Shadow DOM 下的测量/查询问题。
    const { svg } = await mermaid.render(createSvgId(), source, sandbox)
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
      let source = codeEl ? String(codeEl.textContent || '').trim() : ''
      // 切主题重渲染场景下，block 内通常已经被 SVG 替换，此时需要从 data-key 对应的缓存里取 source。
      if (!source) {
        const k = String(block.getAttribute('data-key') || '').trim()
        const cachedSource = k ? _sourceCache.get(k) : null
        source = cachedSource ? String(cachedSource).trim() : ''
      }
      if (!source) {
        // 不要把“没有 source 的历史 SVG”误标为空，避免用户看到图突然消失
        block.setAttribute('data-rendered', '1')
        continue
      }

      // 保存 source，便于放大预览时一键复制 Mermaid 语句
      const key = block.getAttribute('data-key') || hashMermaidSource(source)
      rememberMermaidSource(key, source)

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

/**
 * 重新渲染指定根节点下所有 Mermaid 图（用于主题切换）。
 * 说明：不清空旧 SVG，先标记为待渲染，渲染完成后直接替换，避免“空白闪一下”。
 * @param {HTMLElement} rootEl
 */
export async function rerenderMermaidInElement(rootEl) {
  if (!rootEl || typeof rootEl.querySelectorAll !== 'function') return
  const blocks = Array.from(rootEl.querySelectorAll('.msg-mermaid[data-rendered="1"]'))
  if (blocks.length === 0) return
  for (const block of blocks) {
    block.setAttribute('data-rendered', '0')
  }
  await renderMermaidInElement(rootEl)
}

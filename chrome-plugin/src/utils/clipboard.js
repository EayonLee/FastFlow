/**
 * 剪贴板工具（统一处理兼容性）
 * - 在部分页面（尤其是 http / 权限受限）中 navigator.clipboard 可能不可用
 * - 这里统一提供“先 Clipboard API，失败用 execCommand”的策略
 */

/**
 * 复制文本到剪贴板。
 * @param {string} text
 * @returns {Promise<boolean>} 是否复制成功
 */
export async function copyTextToClipboard(text) {
  if (!text) return false

  // 1) 优先 Clipboard API（现代浏览器）
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch (_) {
    // ignore
  }

  // 2) 兜底：execCommand（兼容性最好）
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '0'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
    return true
  } catch (_) {
    return false
  }
}


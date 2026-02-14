import { ref } from 'vue'
import { copyTextToClipboard } from '@/utils/clipboard.js'

// 默认“已复制”提示的展示时长（毫秒）
const DEFAULT_TIMEOUT_MS = 1500

export function useCopyFeedback(options = {}) {
  // 复制成功状态（key: messageId -> boolean）
  const copiedMap = ref(new Map())
  // 提示持续时长
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS

  // 将 messageId 标记为已复制，并在超时后清除
  function markCopied(messageId) {
    if (!messageId) return
    const map = new Map(copiedMap.value)
    map.set(messageId, true)
    copiedMap.value = map
    window.setTimeout(() => {
      const next = new Map(copiedMap.value)
      next.delete(messageId)
      copiedMap.value = next
    }, timeoutMs)
  }

  // 执行复制（优先 clipboard API，失败走兜底）
  async function copyText(content, messageId) {
    if (!content) return
    const ok = await copyTextToClipboard(content)
    if (!ok) return
    markCopied(messageId)
  }

  return {
    copiedMap,
    copyText
  }
}

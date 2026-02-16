// 默认打字机速度配置（每帧输出字符数与间隔）
const DEFAULT_CHARS_PER_TICK = 1
const DEFAULT_INTERVAL_MS = 16

/**
 * 流式文本打字机渲染
 * 用途：将后端一次返回的大 chunk 也按字符节奏展示，避免“整段突变”体验。
 */
export function useStreamTypewriter(options = {}) {
  const charsPerTick = options.charsPerTick ?? DEFAULT_CHARS_PER_TICK
  const intervalMs = options.intervalMs ?? DEFAULT_INTERVAL_MS
  const onText = options.onText

  // key: messageId -> 当前消息的打字状态
  const stateMap = new Map()

  // 读取或创建状态对象
  function ensureState(messageId) {
    let state = stateMap.get(messageId)
    if (!state) {
      state = {
        buffer: '',
        timerId: null,
        waiters: []
      }
      stateMap.set(messageId, state)
    }
    return state
  }

  // 消费一段缓冲文本并触发下一帧
  function tick(messageId) {
    const state = stateMap.get(messageId)
    if (!state) return

    if (!state.buffer) {
      state.timerId = null
      // 已输出完，通知所有等待 drain 的调用方
      while (state.waiters.length) {
        const resolve = state.waiters.shift()
        resolve()
      }
      stateMap.delete(messageId)
      return
    }

    const piece = state.buffer.slice(0, charsPerTick)
    state.buffer = state.buffer.slice(charsPerTick)
    if (piece && onText) onText(messageId, piece)
    state.timerId = window.setTimeout(() => tick(messageId), intervalMs)
  }

  // 入队一段文本（按打字机方式渐进输出）
  function enqueue(messageId, text) {
    if (!messageId || !text) return
    const state = ensureState(messageId)
    state.buffer += text
    if (state.timerId == null) {
      state.timerId = window.setTimeout(() => tick(messageId), intervalMs)
    }
  }

  // 等待指定消息输出完所有已入队文本
  function drain(messageId) {
    const state = stateMap.get(messageId)
    if (!state || (!state.buffer && state.timerId == null)) {
      return Promise.resolve()
    }
    return new Promise((resolve) => {
      state.waiters.push(resolve)
    })
  }

  // 清理单条消息的打字机状态
  function clear(messageId) {
    const state = stateMap.get(messageId)
    if (!state) return
    if (state.timerId != null) {
      window.clearTimeout(state.timerId)
      state.timerId = null
    }
    state.buffer = ''
    while (state.waiters.length) {
      const resolve = state.waiters.shift()
      resolve()
    }
    stateMap.delete(messageId)
  }

  // 清理所有消息状态
  function cleanup() {
    for (const messageId of stateMap.keys()) {
      clear(messageId)
    }
  }

  return {
    enqueue,
    drain,
    clear,
    cleanup
  }
}

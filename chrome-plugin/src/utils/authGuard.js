import { CONFIG } from '@/config/index.js'
import { AUTHORIZATION_KEY, authService } from '@/services/auth.js'
import { cache } from '@/utils/cache.js'

/**
 * 统一登录态守卫
 * 职责：
 * 1) 定时校验登录状态
 * 2) 监听 Authorization 变化
 * 3) 监听登录过期事件
 */
export function createAuthGuard(options = {}) {
  const {
    // 定时校验间隔，默认走配置
    intervalMs = CONFIG.AUTH_CHECK_INTERVAL_MS,
    // 登录态变化回调：true=已登录，false=未登录/过期
    onAuthedChange
  } = options

  let timer = null
  let unsubscribe = null
  let authed = null

  // 统一设置登录态，避免重复触发
  function setAuthed(val) {
    if (authed === val) return
    authed = val
    if (onAuthedChange) onAuthedChange(val)
  }

  // 统一校验逻辑：无 token 直接判定未登录；有 token 则服务端校验
  async function verify() {
    const token = await cache.get(AUTHORIZATION_KEY)
    if (!token) {
      setAuthed(false)
      return false
    }

    try {
      await authService.checkLogin()
      setAuthed(true)
      return true
    } catch (e) {
      setAuthed(false)
      return false
    }
  }

  function handleAuthExpired() {
    setAuthed(false)
  }

  // 启动守卫（幂等）
  async function start() {
    await verify()

    if (!timer) {
      timer = setInterval(() => {
        verify()
      }, intervalMs)
    }

    if (!unsubscribe) {
      unsubscribe = cache.onChanged((changes) => {
        const authChange = changes?.[AUTHORIZATION_KEY]
        if (!authChange) return

        if (!authChange.newValue) {
          setAuthed(false)
          return
        }

        setAuthed(true)
        verify()
      })
    }

    window.addEventListener(authService.getAuthExpiredEventName(), handleAuthExpired)
  }

  // 停止守卫
  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    if (unsubscribe) {
      unsubscribe()
      unsubscribe = null
    }
    window.removeEventListener(authService.getAuthExpiredEventName(), handleAuthExpired)
  }

  return {
    start,
    stop,
    verify,
    getAuthed: () => authed
  }
}

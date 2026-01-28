import { reactive, computed } from 'vue'
import { getUserInfo } from '@/services/userService'

// 登录 token
const STATE_KEY_TOKEN = 'Authorization'
// 当前登录用户 uid
const STATE_KEY_UID = 'uid'
// 用户信息快照 (用于提升首屏体验)
const STATE_KEY_USER_SNAPSHOT = 'user_snapshot'

// State (singleton)
const state = reactive({
  token: localStorage.getItem(STATE_KEY_TOKEN) || '',
  uid: localStorage.getItem(STATE_KEY_UID) || '',
  // 优先使用快照初始化，避免页面刷新时的"User"闪烁
  userInfo: JSON.parse(localStorage.getItem(STATE_KEY_USER_SNAPSHOT) || '{}')
})

export const useUserStore = () => {
  const isLoggedIn = computed(() => !!state.token)
  
  const userName = computed(() => state.userInfo?.username || 'User')
  const userAvatar = computed(() => (state.userInfo?.username?.[0] || 'U').toUpperCase())

  const login = (data: { token: string, userInfo: any }) => {
    state.token = data.token
    state.uid = data.userInfo.uid
    state.userInfo = data.userInfo
    
    localStorage.setItem(STATE_KEY_TOKEN, data.token)
    localStorage.setItem(STATE_KEY_UID, String(data.userInfo.uid))
    // 保存快照
    localStorage.setItem(STATE_KEY_USER_SNAPSHOT, JSON.stringify(data.userInfo))
  }

  const logout = () => {
    state.token = ''
    state.uid = ''
    state.userInfo = {}
    
    localStorage.removeItem(STATE_KEY_TOKEN)
    localStorage.removeItem(STATE_KEY_UID)
    localStorage.removeItem(STATE_KEY_USER_SNAPSHOT)
  }

  const checkAndRefreshUserInfo = async () => {
    if (!state.token || !state.uid) return

    // 始终尝试刷新最新数据 (Stale-While-Revalidate 策略)
    try {
      const res = await getUserInfo()
      if (res) {
        state.userInfo = res
        // 更新快照
        localStorage.setItem(STATE_KEY_USER_SNAPSHOT, JSON.stringify(res))
      }
    } catch (e) {
      console.error('Failed to refresh user info', e)
    }
  }

  return {
    state,
    isLoggedIn,
    userName,
    userAvatar,
    login,
    logout,
    checkAndRefreshUserInfo
  }
}

<script setup>
/**
 * Popup 组件
 * 作用：Chrome 插件的弹出窗口，用于显示状态、设置或快捷操作。
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import Header from '@/components/Header.vue'
import { authService } from '@/services/auth.js'
import { cache } from '@/utils/cache.js'
import { createAuthGuard } from '@/utils/authGuard.js'
import Landing from './views/Landing.vue'
import Login from './views/Login.vue'
import Register from './views/Register.vue'
import Dashboard from './views/Dashboard.vue'

// 简单的路由状态管理
const AUTH_VIEWS = new Set(['landing', 'login', 'register'])
const currentView = ref('landing')
const user = ref(null)
// 监听路由变化并持久化
watch(currentView, (newView) => {
  cache.set('lastView', newView)
})

// 检查是否已登录
const isLoggedIn = computed(() => !!user.value)

// 导航处理
function navigateTo(view) {
  currentView.value = view
}

// 登录成功处理
function handleLoginSuccess(userData) {
  user.value = userData
  // 跳转到仪表盘
  currentView.value = 'dashboard'
}

let authGuard = null

// 同步用户信息与视图
async function syncSession() {
  const savedView = await cache.get('lastView')
  if (savedView) {
    currentView.value = savedView
  }

  const savedUser = await authService.getCurrentUser()
  const token = await authService.getToken()

  if (!savedUser || !token) {
    user.value = null
    if (currentView.value === 'dashboard') {
      currentView.value = 'landing'
    }
    return
  }

  user.value = savedUser
  if (AUTH_VIEWS.has(currentView.value)) {
    currentView.value = 'dashboard'
  }
}

function handleLogout() {
  user.value = null
  authService.logout()
  cache.remove('user')
  cache.remove('token')
  cache.remove('lastView') // 清除视图状态
  currentView.value = 'landing'
  stopAuthPolling()
}

function handleHeaderClick() {
  if (isLoggedIn.value) {
    currentView.value = 'dashboard'
  } else {
    currentView.value = 'landing'
  }
}

// 定时轮询登录状态，处理会话过期
function startAuthPolling() {
  stopAuthPolling()
  authGuard = createAuthGuard({
    onAuthedChange: (val) => {
      if (!val) {
        // 未登录/过期：清理 UI 状态
        user.value = null
        currentView.value = 'landing'
        return
      }
      // 已登录：同步用户信息与视图
      syncSession()
    }
  })
  authGuard.start()
}

function stopAuthPolling() {
  if (authGuard) {
    authGuard.stop()
    authGuard = null
  }
}

onMounted(() => {
  syncSession()
  startAuthPolling()
})

onUnmounted(() => {
  stopAuthPolling()
})
</script>

<template>
  <div class="popup-container">
    <Header @title-click="handleHeaderClick" />
    
    <div class="content-wrapper">
      <transition name="fade" mode="out-in">
        <!-- Landing View -->
        <Landing 
          v-if="currentView === 'landing'" 
          @navigate="navigateTo" 
        />
        
        <!-- Login View -->
        <Login 
          v-else-if="currentView === 'login'" 
          @navigate="navigateTo"
          @login-success="handleLoginSuccess"
        />
        
        <!-- Register View -->
        <Register 
          v-else-if="currentView === 'register'" 
          @navigate="navigateTo"
        />
        
        <!-- Dashboard View -->
        <Dashboard 
          v-else-if="currentView === 'dashboard' && user" 
          :user="user"
          @logout="handleLogout"
        />
      </transition>
    </div>

    <div class="footer">
      <div class="footer-content">
        <span>@ 2026 Fast<span class="highlight">Flow</span></span>
        <span class="divider">|</span>
        <span>Created By <span class="highlight">lizhengtai@360.cn</span></span>
      </div>
    </div>
  </div>
</template>

<style>
/* Global reset for Popup */
body {
  margin: 0;
  padding: 0;
  background-color: var(--bg-app);
  color: var(--text-primary);
  transition: background-color 0.3s, color 0.3s;
}
</style>

<style scoped>
.popup-container {
  width: 320px; /* 稍微加宽一点以适应表单 */
  min-height: 400px;
  background-color: var(--bg-app);
  color: var(--text-primary);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  border: none; /* 移除黑色边框 */
  display: flex;
  flex-direction: column;
  transition: background-color 0.3s, color 0.3s;
}

.content-wrapper {
  flex: 1;
  position: relative;
  overflow-y: auto;
}

.status-info h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  color: var(--text-primary);
}

.status-info p {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.footer {
  padding: 12px 16px;
  display: flex;
  justify-content: center; /* Center align for better balance with new content */
  font-size: 10px; /* Slightly smaller for copyright info */
  color: var(--text-dim);
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-app);
  z-index: 10;
  transition: background-color 0.3s, border-color 0.3s;
}

.footer-content {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.highlight {
  color: var(--accent-neon);
  font-weight: 500;
}

.divider {
  color: var(--border-subtle);
}
</style>

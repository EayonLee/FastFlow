<script setup lang="ts">
import { onMounted, ref, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/userStore'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
  transparent?: boolean
}>()

const { t, locale } = useI18n()
const router = useRouter()
const userStore = useUserStore()
const { showToast } = useToast()
const { isLoggedIn, userAvatar, userName } = userStore
const { checkAndRefreshUserInfo, logout } = userStore

const showDropdown = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value
}

const closeDropdown = (e: MouseEvent) => {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
    showDropdown.value = false
  }
}

const handleLogout = () => {
  logout()
  showToast(t('common.logout_success'), 'success')
  router.push('/')
  showDropdown.value = false
}

onMounted(() => {
  checkAndRefreshUserInfo()
  document.addEventListener('click', closeDropdown)
})

onUnmounted(() => {
  document.removeEventListener('click', closeDropdown)
})

const toggleLocale = () => {
  locale.value = locale.value === 'en' ? 'zh' : 'en'
}

const goHome = () => {
  router.push('/')
}
</script>

<template>
  <header class="global-header" :class="{ transparent: props.transparent }">
    <div class="brand" @click="goHome">
      <span class="brand-text">FAST<span class="neon">FLOW</span></span>
      <span class="brand-tag">BETA</span>
    </div>
    
    <div class="header-extra-left">
      <slot name="extra"></slot>
    </div>

    <div class="right-area">
      <div class="actions">
        <button class="lang-btn" @click="toggleLocale">
          {{ locale === 'en' ? '🇨🇳 中文' : '🇺🇸 EN' }}
        </button>
        
        <div class="user-profile-wrapper" v-if="isLoggedIn" ref="dropdownRef">
          <div class="user-profile" @click="toggleDropdown">
            <div class="avatar">{{ userAvatar }}</div>
            <span class="username">{{ userName }}</span>
            <svg class="chevron" :class="{ open: showDropdown }" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </div>
          
          <div class="dropdown-menu" v-show="showDropdown">
            <div class="dropdown-item" @click="handleLogout">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
              <span>{{ t('common.logout') }}</span>
            </div>
          </div>
        </div>
        
        <div class="auth-buttons" v-else>
          <button class="auth-btn login" @click="router.push('/login')">
            {{ t('common.login') }}
          </button>
          <button class="auth-btn register" @click="router.push('/register')">
            {{ t('common.register') }}
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.global-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-subtle);
  z-index: 100;
  transition: all 0.3s ease;
  width: 100%;
  box-sizing: border-box;
}

.global-header.transparent {
  background: transparent;
  border-bottom: 1px solid transparent;
  position: absolute;
  top: 0;
  left: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.brand-text {
  font-family: var(--font-mono);
  font-weight: 800;
  font-size: 24px;
  letter-spacing: -1px;
  color: var(--text-primary);
}

.brand-tag {
  font-size: 10px;
  background: var(--border-subtle);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.neon {
  color: var(--accent-neon);
  text-shadow: 0 0 10px var(--accent-neon-dim);
}

.right-area {
  display: flex;
  align-items: center;
  gap: clamp(12px, 2vw, 24px);
  margin-left: auto;
  flex-shrink: 0;
}

.header-extra-left {
  display: flex;
  align-items: center;
  margin-left: 16px;
  flex: 1;
  margin-right: clamp(12px, 2vw, 24px);
  min-width: 0;
}

.actions {
  display: flex;
  align-items: center;
  gap: clamp(10px, 1.5vw, 16px);
}

.lang-btn {
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  padding: 4px 10px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: var(--font-mono);
  border-radius: 4px;
}

.lang-btn:hover {
  border-color: var(--text-primary);
  color: var(--text-primary);
}

.user-profile-wrapper {
  position: relative;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
  max-width: clamp(110px, 14vw, 170px);
  flex: 0 1 auto;
}

.user-profile:hover {
  background: rgba(255, 255, 255, 0.05);
}

.chevron {
  color: var(--text-secondary);
  transition: transform 0.2s;
}

.chevron.open {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  min-width: 140px;
  z-index: 1000;
  overflow: hidden;
  animation: slideDown 0.2s ease;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.2s;
  font-family: var(--font-mono);
  font-size: 13px;
}

.dropdown-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--accent-neon);
}

.dropdown-item svg {
  color: var(--text-secondary);
}

.dropdown-item:hover svg {
  color: var(--accent-neon);
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.avatar {
  width: 24px;
  height: 24px;
  background: var(--accent-neon);
  color: #000;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 12px;
  font-family: var(--font-mono);
}

.username {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  max-width: clamp(64px, 9vw, 120px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.auth-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
}

.auth-btn {
  padding: 6px 16px;
  border-radius: 4px;
  font-size: 13px;
  font-family: var(--font-mono);
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
}

.auth-btn.login {
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
}

.auth-btn.login:hover {
  border-color: var(--text-primary);
  color: var(--text-primary);
}

.auth-btn.register {
  background: var(--accent-neon);
  border: 1px solid var(--accent-neon);
  color: #000;
  font-weight: 600;
}

.auth-btn.register:hover {
  background: #00ff41; /* Slightly brighter or same */
  box-shadow: 0 0 12px var(--accent-neon-dim);
  transform: translateY(-1px);
}
</style>

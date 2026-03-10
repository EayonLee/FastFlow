<script setup>
import { cache } from '@/utils/cache.js'
import { authService } from '@/services/auth.js'
import NeonButton from '@/components/NeonButton.vue'
import { onMounted, ref, watch } from 'vue'
import { getEmailError, getPasswordError } from '@/utils/validators.js'

const emit = defineEmits(['navigate', 'login-success'])

const form = ref({
  email: '',
  password: ''
})

const errors = ref({
  email: '',
  password: ''
})

const isLoading = ref(false)
const rememberAccount = ref(false)

const LOGIN_FORM_CACHE_KEY = 'login_form_cache'
const REMEMBER_ACCOUNT_KEY = 'remembered_account'
const LOGIN_FORM_TTL = 5 * 60 * 1000

// 监听表单变化并保存到 chrome.storage.local（临时缓存，非记住账号）
watch(form, (newVal) => {
  // 只在未记住账号的情况下缓存输入内容，避免覆盖记住的账号
  if (!rememberAccount.value) {
    cache.setWithTTL(LOGIN_FORM_CACHE_KEY, newVal, LOGIN_FORM_TTL) // 5分钟过期
  }
}, { deep: true })

onMounted(async () => {
  const savedAccount = await cache.get(REMEMBER_ACCOUNT_KEY)
  if (savedAccount) {
    try {
      const { email, password } = typeof savedAccount === 'string' ? JSON.parse(savedAccount) : savedAccount
      form.value.email = email
      form.value.password = password
      rememberAccount.value = true
    } catch (e) {
      // 兼容旧格式（只存了邮箱）
      form.value.email = savedAccount
      rememberAccount.value = true
    }
  } else {
    // 如果没有记住账号，尝试恢复临时缓存
    const cachedForm = await cache.getWithTTL(LOGIN_FORM_CACHE_KEY)
    if (cachedForm) {
      form.value.email = cachedForm.email || ''
      form.value.password = cachedForm.password || ''
    }
  }
})

function clearError(field) {
  errors.value[field] = ''
  globalError.value = ''
}

function applyFieldErrors(fieldErrors) {
  let hasFieldError = false
  if (!fieldErrors || typeof fieldErrors !== 'object') return hasFieldError
  const fieldMap = {
    email: 'email',
    password: 'password'
  }
  Object.entries(fieldMap).forEach(([backendField, formField]) => {
    if (fieldErrors[backendField]) {
      errors.value[formField] = fieldErrors[backendField]
      hasFieldError = true
    }
  })
  return hasFieldError
}

const globalError = ref('')

async function handleLogin() {
  // Reset errors
  errors.value.email = ''
  errors.value.password = ''
  globalError.value = ''

  let hasError = false

  const emailError = getEmailError(form.value.email)
  if (emailError) {
    errors.value.email = emailError
    hasError = true
  }

  const passwordError = getPasswordError(form.value.password)
  if (passwordError) {
    errors.value.password = passwordError
    hasError = true
  }

  if (hasError) return

  isLoading.value = true

  try {
    const user = await authService.login(form.value.email, form.value.password)
    
    // 登录成功后清除临时缓存
    await cache.removeWithTTL(LOGIN_FORM_CACHE_KEY)

    // 记住账号逻辑：
    // 如果勾选了记住账号，保存邮箱和加密后的密码
    if (rememberAccount.value) {
      await cache.set(REMEMBER_ACCOUNT_KEY, {
        email: form.value.email,
        password: form.value.password
      })
    } else {
      await cache.remove(REMEMBER_ACCOUNT_KEY)
    }
    
    emit('login-success', user)
  } catch (error) {
    console.error('[FastFlow] Login failed:', error)
    if (error.message.includes('Failed to fetch')) {
      globalError.value = '无法连接到服务器，请检查网络或稍后重试'
    } else if (!applyFieldErrors(error?.fieldErrors)) {
      errors.value.password = error.message || '登录失败，请检查账号密码'
    } else {
      globalError.value = ''
    }
  } finally {
    isLoading.value = false
  }
}

function goToRegister() {
  emit('navigate', 'register')
}
</script>

<template>
  <div class="auth-view">
    <form @submit.prevent="handleLogin" class="auth-form" novalidate>
      <div class="form-group">
        <label>邮箱</label>
        <input 
          v-model="form.email" 
          type="email" 
          placeholder="请输入 @360.cn 邮箱"
          :class="{ 'error': errors.email }"
          @input="clearError('email')"
          novalidate
        >
        <div class="error-msg" v-if="errors.email">{{ errors.email }}</div>
      </div>
      
      <div class="form-group">
        <label>密码</label>
        <input 
          v-model="form.password" 
          type="password" 
          placeholder="请输入6-22位密码（支持 _-@!#$%&*）"
          :class="{ 'error': errors.password }"
          @input="clearError('password')"
        >
        <div class="error-msg" v-if="errors.password">{{ errors.password }}</div>
      </div>
      
      <div class="form-options">
        <label class="checkbox-label">
          <input type="checkbox" v-model="rememberAccount">
          <span class="checkmark"></span>
          记住账号
        </label>
      </div>

      <div class="global-error" v-if="globalError">{{ globalError }}</div>

      <NeonButton type="submit" full-width :disabled="isLoading">
        {{ isLoading ? '登录中...' : '登录' }}
      </NeonButton>
    </form>

    <div class="auth-footer">
      <p class="switch-text">
        没有账号？ 
        <a @click.prevent="goToRegister" href="#">立即注册</a>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-view {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.form-group input {
  width: 100%;
  padding: 10px;
  background: color-mix(in srgb, var(--bg-surface) 88%, transparent);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus {
  border-color: var(--accent-neon);
}

.form-group input.error {
  border-color: var(--danger);
}

.error-msg {
  color: var(--danger);
  font-size: 11px;
  margin-top: 4px;
}

.form-options {
  margin-bottom: 20px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
}

.checkbox-label input {
  display: none;
}

.checkmark {
  width: 14px;
  height: 14px;
  border: 1px solid var(--border-subtle);
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--bg-surface) 88%, transparent);
}

.checkbox-label input:checked + .checkmark {
  background: var(--accent-neon);
  border-color: var(--accent-neon);
}

.checkbox-label input:checked + .checkmark::after {
  content: '✓';
  color: #000;
  font-size: 10px;
  font-weight: bold;
}

.global-error {
  color: var(--danger);
  font-size: 12px;
  margin-bottom: 12px;
  text-align: center;
  background: rgba(255, 59, 48, 0.1);
  padding: 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 59, 48, 0.2);
}

.auth-footer {
  margin-top: 20px;
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
}

.auth-footer a {
  color: var(--accent-neon);
  text-decoration: none;
  margin-left: 4px;
}

.auth-footer a:hover {
  text-decoration: underline;
}
</style>

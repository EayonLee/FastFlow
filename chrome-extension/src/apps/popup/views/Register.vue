<script setup>
import { cache } from '@/shared/utils/cache.js'
import { authService } from '@/shared/services/auth.js'
import NeonButton from '@/shared/components/NeonButton.vue'
import { onMounted, ref, watch } from 'vue'
import {
  getEmailError,
  getInviteCodeError,
  getPasswordError,
  getUsernameError
} from '@/shared/utils/validators.js'

const emit = defineEmits(['navigate'])

const form = ref({
  username: '',
  email: '',
  inviteCode: '',
  password: '',
  confirmPassword: ''
})

const REGISTER_FORM_CACHE_KEY = 'register_form_cache'
const REGISTER_FORM_TTL = 5 * 60 * 1000

// 监听表单变化并保存到 chrome.storage.local（临时缓存）
watch(form, (newVal) => {
  cache.setWithTTL(REGISTER_FORM_CACHE_KEY, newVal, REGISTER_FORM_TTL) // 5分钟过期
}, { deep: true })

onMounted(async () => {
  // 尝试恢复临时缓存
  const cachedForm = await cache.getWithTTL(REGISTER_FORM_CACHE_KEY)
  if (cachedForm) {
    form.value = { ...form.value, ...cachedForm }
  }
})

const errors = ref({
  username: '',
  email: '',
  inviteCode: '',
  password: '',
  confirmPassword: ''
})

const isLoading = ref(false)
const globalError = ref('')

function clearError(field) {
  errors.value[field] = ''
  globalError.value = ''
}

function resetErrors() {
  Object.keys(errors.value).forEach((key) => {
    errors.value[key] = ''
  })
  globalError.value = ''
}

function applyFieldErrors(fieldErrors) {
  let hasFieldError = false
  if (!fieldErrors || typeof fieldErrors !== 'object') return hasFieldError
  const fieldMap = {
    username: 'username',
    email: 'email',
    inviteCode: 'inviteCode',
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

async function handleRegister() {
  resetErrors()
  errors.value.username = getUsernameError(form.value.username)
  errors.value.email = getEmailError(form.value.email)
  errors.value.inviteCode = getInviteCodeError(form.value.inviteCode)
  errors.value.password = getPasswordError(form.value.password)
  if (!form.value.confirmPassword) {
    errors.value.confirmPassword = '请确认密码'
  } else if (form.value.password !== form.value.confirmPassword) {
    errors.value.confirmPassword = '两次密码不一致'
  }
  const hasError = Object.values(errors.value).some((message) => Boolean(message))
  if (hasError) {
    return
  }

  isLoading.value = true

  try {
    await authService.register({
      username: form.value.username,
      email: form.value.email,
      password: form.value.password,
      inviteCode: form.value.inviteCode
    })
    await cache.removeWithTTL(REGISTER_FORM_CACHE_KEY)
    emit('navigate', 'login')
  } catch (error) {
    console.error('[FastFlow] Register failed:', error)
    const hasFieldError = applyFieldErrors(error?.fieldErrors)
    if (!hasFieldError) {
      globalError.value = error.message || '注册失败'
    }
  } finally {
    isLoading.value = false
  }
}

function goToLogin() {
  emit('navigate', 'login')
}
</script>

<template>
  <div class="auth-view">
    <form @submit.prevent="handleRegister" class="auth-form" novalidate>
      <div class="form-group">
        <label>用户名</label>
        <input 
          v-model="form.username"
          type="text" 
          placeholder="请输入5-12位中英文或数字"
          :class="{ 'error': errors.username }"
          @input="clearError('username')"
        >
        <div class="error-msg" v-if="errors.username">{{ errors.username }}</div>
      </div>

      <div class="form-group">
        <label>邮箱</label>
        <input 
          v-model="form.email" 
          type="email" 
          placeholder="请输入 @360.cn 邮箱"
          :class="{ 'error': errors.email }"
          @input="clearError('email')"
        >
        <div class="error-msg" v-if="errors.email">{{ errors.email }}</div>
      </div>

      <div class="form-group">
        <label>邀请码</label>
        <input
          v-model="form.inviteCode"
          type="text"
          placeholder="请输入6位邀请码"
          :class="{ 'error': errors.inviteCode }"
          @input="clearError('inviteCode')"
        >
        <div class="error-msg" v-if="errors.inviteCode">{{ errors.inviteCode }}</div>
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

      <div class="form-group">
        <label>确认密码</label>
        <input 
          v-model="form.confirmPassword" 
          type="password" 
          :class="{ 'error': errors.confirmPassword }"
          @input="clearError('confirmPassword')"
        >
        <div class="error-msg" v-if="errors.confirmPassword">{{ errors.confirmPassword }}</div>
      </div>

      <div class="error-msg global-error" v-if="globalError">{{ globalError }}</div>

      <NeonButton type="submit" full-width :disabled="isLoading" style="margin-top: 8px;">
        {{ isLoading ? '注册中...' : '注册' }}
      </NeonButton>
    </form>

    <div class="auth-footer">
      <p class="switch-text">
        已有账号？ 
        <a @click.prevent="goToLogin" href="#">去登录</a>
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

.global-error {
  margin-top: 8px;
  text-align: center;
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

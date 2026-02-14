<script setup>
import { cache } from '@/utils/cache.js'
import { authService } from '@/services/auth.js'
import NeonButton from '@/components/NeonButton.vue'
import { onMounted, ref, watch } from 'vue'
import validator from 'validator'

const emit = defineEmits(['navigate'])

const form = ref({
  name: '',
  email: '',
  code: '',
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
  name: '',
  email: '',
  code: '',
  password: '',
  confirmPassword: ''
})

const isLoading = ref(false)
const codeTimer = ref(0)
let timerInterval = null

function clearError(field) {
  errors.value[field] = ''
}

function validateEmail(email) {
  return validator.isEmail(email)
}

function startTimer() {
  if (codeTimer.value > 0) return
  codeTimer.value = 60
  timerInterval = setInterval(() => {
    codeTimer.value--
    if (codeTimer.value <= 0 && timerInterval) {
      clearInterval(timerInterval)
      timerInterval = null
    }
  }, 1000)
}

function sendCode() {
  errors.value.email = ''
  if (!form.value.email) {
    errors.value.email = '请输入邮箱'
    return
  } else if (!validateEmail(form.value.email)) {
    errors.value.email = '邮箱格式不正确'
    return
  }
  
  // Mock send code
  console.info('[FastFlow] Sending code to', form.value.email)
  startTimer()
}

function resetErrors() {
  Object.keys(errors.value).forEach((key) => {
    errors.value[key] = ''
  })
}

async function handleRegister() {
  // Reset errors
  resetErrors()
  
  let hasError = false

  if (!form.value.name) {
    errors.value.name = '请输入用户名'
    hasError = true
  }

  if (!form.value.email) {
    errors.value.email = '请输入邮箱'
    hasError = true
  } else if (!validateEmail(form.value.email)) {
    errors.value.email = '邮箱格式不正确'
    hasError = true
  }

  if (!form.value.code) {
    errors.value.code = '请输入验证码'
    hasError = true
  }

  if (!form.value.password) {
    errors.value.password = '请输入密码'
    hasError = true
  }

  if (!form.value.confirmPassword) {
    errors.value.confirmPassword = '请确认密码'
    hasError = true
  } else if (form.value.password !== form.value.confirmPassword) {
    errors.value.confirmPassword = '两次密码不一致'
    hasError = true
  }

  if (hasError) return

  isLoading.value = true

  try {
    await authService.register({
      username: form.value.name,
      email: form.value.email,
      password: form.value.password,
      code: form.value.code
    })
    
    // 注册成功后清除缓存
    await cache.removeWithTTL(REGISTER_FORM_CACHE_KEY)

    // 注册成功后跳转登录
    emit('navigate', 'login')
  } catch (error) {
    console.error('[FastFlow] Register failed:', error)
    // 这里简单处理，假设是邮箱被占用的错误，实际应根据后端返回
    errors.value.email = error.message || '注册失败'
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
          v-model="form.name" 
          type="text" 
          placeholder="您的称呼" 
          :class="{ 'error': errors.name }"
          @input="clearError('name')"
        >
        <div class="error-msg" v-if="errors.name">{{ errors.name }}</div>
      </div>

      <div class="form-group">
        <label>邮箱</label>
        <input 
          v-model="form.email" 
          type="email" 
          placeholder="your@email.com" 
          :class="{ 'error': errors.email }"
          @input="clearError('email')"
        >
        <div class="error-msg" v-if="errors.email">{{ errors.email }}</div>
      </div>

      <div class="form-group code-group">
        <div class="input-wrapper">
          <label>验证码</label>
          <input 
            v-model="form.code" 
            type="text" 
            placeholder="6位数字" 
            :class="{ 'error': errors.code }"
            @input="clearError('code')"
          >
          <div class="error-msg" v-if="errors.code">{{ errors.code }}</div>
        </div>
        <NeonButton
          type="button"
          class="btn-code"
          :disabled="codeTimer > 0"
          @click="sendCode"
        >
          {{ codeTimer > 0 ? `${codeTimer}s` : '获取验证码' }}
        </NeonButton>
      </div>
      
      <div class="form-group">
        <label>密码</label>
        <input 
          v-model="form.password" 
          type="password" 
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

.code-group {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.code-group .input-wrapper {
  flex: 1;
}

.btn-code {
  /* 复用 NeonButton 的整体风格，但尺寸更紧凑，保证和输入框对齐 */
  height: 38px;
  margin-bottom: 2px;
  padding: 0 12px !important;
  font-size: 12px !important;
  white-space: nowrap;
}

.btn-code:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

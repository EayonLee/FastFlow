<script setup>
import { ref, onMounted, watch } from 'vue'
import { authService } from '@/services/auth.js'
import NeonButton from '@/components/NeonButton.vue'
import { cache } from '@/utils/cache.js'

const emit = defineEmits(['navigate'])

const form = ref({
  name: '',
  email: '',
  code: '',
  password: '',
  confirmPassword: ''
})

// 监听表单变化并保存到 chrome.storage.local（临时缓存）
watch(form, (newVal) => {
  cache.setWithTTL('register_form_cache', newVal, 5 * 60 * 1000) // 5分钟过期
}, { deep: true })

onMounted(async () => {
  // 尝试恢复临时缓存
  const cachedForm = await cache.getWithTTL('register_form_cache')
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

const clearError = (field) => {
  errors.value[field] = ''
}

import validator from 'validator'

// ... existing code ...

const validateEmail = (email) => {
  return validator.isEmail(email)
}

const startTimer = () => {
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

const sendCode = () => {
  errors.value.email = ''
  if (!form.value.email) {
    errors.value.email = '请输入邮箱'
    return
  } else if (!validateEmail(form.value.email)) {
    errors.value.email = '邮箱格式不正确'
    return
  }
  
  // Mock send code
  console.log('Sending code to', form.value.email)
  startTimer()
}

const handleRegister = async () => {
  // Reset errors
  Object.keys(errors.value).forEach(key => errors.value[key] = '')
  
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
    await cache.removeWithTTL('register_form_cache')

    // 注册成功后跳转登录
    emit('navigate', 'login')
  } catch (error) {
    console.error('Register failed:', error)
    // 这里简单处理，假设是邮箱被占用的错误，实际应根据后端返回
    errors.value.email = error.message || '注册失败'
  } finally {
    isLoading.value = false
  }
}

const goToLogin = () => {
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
        <button 
          type="button" 
          class="btn-code" 
          :disabled="codeTimer > 0"
          @click="sendCode"
        >
          {{ codeTimer > 0 ? `${codeTimer}s` : '获取验证码' }}
        </button>
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

      <NeonButton full-width :disabled="isLoading" @click="handleRegister" style="margin-top: 8px;">
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
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: #fff;
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
  height: 38px; /* Match input height roughly */
  margin-bottom: 2px; /* Align visual bottom */
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid var(--border-subtle);
  color: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  padding: 0 12px;
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

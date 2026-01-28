<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AuthLayout from '../../components/auth/AuthLayout.vue'
import { validateName, validateEmail, validatePassword, validateCode } from '@/utils/validators'
import { encrypt } from '@/utils/crypto'
import { register } from '@/services/authService'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const { showToast } = useToast()
const { t } = useI18n()

const form = ref({
  email: '',
  code: '',
  name: '',
  password: '',
  confirmPassword: ''
})

const errors = ref({
  email: '',
  code: '',
  name: '',
  password: '',
  confirmPassword: ''
})

const codeTimer = ref(0)
let timerInterval: any = null

const clearError = (field: keyof typeof errors.value) => {
  errors.value[field] = ''
}

onBeforeUnmount(() => {
  if (timerInterval) clearInterval(timerInterval)
})

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
    errors.value.email = t('auth.email_required')
    return
  } else if (!validateEmail(form.value.email)) {
    errors.value.email = t('auth.invalid_email_format')
    return
  }
  // Mock API call
  console.log('Sending code to', form.value.email)
  startTimer()
}

const handleRegister = () => {
  // Reset errors
  Object.keys(errors.value).forEach(key => errors.value[key as keyof typeof errors.value] = '')

  let hasError = false

  if (!form.value.name) {
    errors.value.name = t('auth.name_required')
    hasError = true
  } else if (!validateName(form.value.name)) {
    errors.value.name = t('auth.invalid_name_format')
    hasError = true
  }

  if (!form.value.email) {
    errors.value.email = t('auth.email_required')
    hasError = true
  } else if (!validateEmail(form.value.email)) {
    errors.value.email = t('auth.invalid_email_format')
    hasError = true
  }

  if (!form.value.code) {
    errors.value.code = t('auth.verification_code_required')
    hasError = true
  } else if (!validateCode(form.value.code)) {
    errors.value.code = t('auth.invalid_code_format')
    hasError = true
  }

  if (!form.value.password) {
    errors.value.password = t('auth.password_required')
    hasError = true
  } else if (!validatePassword(form.value.password)) {
    errors.value.password = t('auth.invalid_password_format')
    hasError = true
  }

  if (!form.value.confirmPassword) {
    errors.value.confirmPassword = t('auth.confirm_password_required')
    hasError = true
  }

  if (!hasError && form.value.password !== form.value.confirmPassword) {
    errors.value.confirmPassword = t('auth.password_mismatch')
    hasError = true
  }

  if (hasError) return
  
  // 加密密码
  const encryptedPassword = encrypt(form.value.password)

  // 调用注册接口
  register({
    username: form.value.name,
    email: form.value.email,
    password: encryptedPassword
  })
  .then((res) => {
    console.log('Register success:', res)
    showToast(t('auth.register_success'), 'success')
    router.push('/login')
  })
  .catch((error: any) => {
    console.error('Register error:', error)
  })
}

const goToLogin = () => {
  router.push('/login')
}
</script>

<template>
  <AuthLayout :title="t('auth.register_title')">
    <form @submit.prevent="handleRegister" class="auth-form" novalidate>
      <div class="form-group">
        <label>{{ t('auth.name_label') }}</label>
        <input 
          v-model="form.name" 
          type="text" 
          :placeholder="t('auth.name_placeholder')" 
          :class="{ 'error': errors.name }"
          @input="clearError('name')"
          @keyup.enter="handleRegister"
        >
        <div class="error-msg" v-if="errors.name">{{ errors.name }}</div>
      </div>

      <div class="form-group">
        <label>{{ t('auth.email_label') }}</label>
        <input 
          v-model="form.email" 
          type="email" 
          :placeholder="t('auth.email_placeholder')" 
          :class="{ 'error': errors.email }"
          @input="clearError('email')"
          @keyup.enter="handleRegister"
        >
        <div class="error-msg" v-if="errors.email">{{ errors.email }}</div>
      </div>
      
      <div class="form-group code-group">
        <div class="input-wrapper">
          <label>{{ t('auth.verification_code_label') }}</label>
          <input 
            v-model="form.code" 
            type="text" 
            :placeholder="t('auth.verification_code_placeholder')" 
            :class="{ 'error': errors.code }"
            @input="clearError('code')"
            @keyup.enter="handleRegister"
          >
          <div class="error-msg" v-if="errors.code">{{ errors.code }}</div>
        </div>
        <button 
          type="button" 
          class="btn-code" 
          :disabled="codeTimer > 0"
          @click="sendCode"
        >
          {{ codeTimer > 0 ? `${codeTimer}s` : t('auth.send_code_btn') }}
        </button>
      </div>

      <div class="form-group">
        <label>{{ t('auth.password_label') }}</label>
        <input 
          v-model="form.password" 
          type="password" 
          :placeholder="t('auth.password_placeholder')" 
          :class="{ 'error': errors.password }"
          @input="clearError('password')"
          @keyup.enter="handleRegister"
        >
        <div class="error-msg" v-if="errors.password">{{ errors.password }}</div>
      </div>

      <div class="form-group">
        <label>{{ t('auth.confirm_password_label') }}</label>
        <input 
          v-model="form.confirmPassword" 
          type="password" 
          :placeholder="t('auth.confirm_password_placeholder')" 
          :class="{ 'error': errors.confirmPassword }"
          @input="clearError('confirmPassword')"
          @keyup.enter="handleRegister"
        >
        <div class="error-msg" v-if="errors.confirmPassword">{{ errors.confirmPassword }}</div>
      </div>

      <button type="submit" class="btn-neon full-width">
        {{ t('auth.register_btn') }}
      </button>
    </form>

    <template #footer>
      <p class="switch-text">
        {{ t('auth.has_account') }} 
        <a @click.prevent="goToLogin" href="#">{{ t('auth.login_link') }}</a>
      </p>
    </template>
  </AuthLayout>
</template>

<style scoped>
/* Specific styles for Register Page */
.code-group {
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  gap: 12px;
}

.code-group .input-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn-code {
  height: 44px; /* Match input height */
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  padding: 0 16px;
  font-family: var(--font-sans);
  font-size: 13px;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
  min-width: 100px;
  font-weight: 500;
  clip-path: none;
}

.btn-code:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.3);
}

.btn-code:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: rgba(255, 255, 255, 0.02);
}
</style>
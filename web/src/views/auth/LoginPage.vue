<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AuthLayout from '../../components/auth/AuthLayout.vue'
import { validateEmail, validatePassword } from '@/utils/validators'
import { encrypt, decrypt } from '@/utils/crypto'
import { login } from '@/services/authService'
import { useUserStore } from '@/stores/userStore'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const { showToast } = useToast()

const form = ref({
  email: '',
  password: ''
})

const rememberAccount = ref(false)

const errors = ref({
  email: '',
  password: ''
})

onMounted(() => {
  const savedEmail = localStorage.getItem('remembered_account')
  const savedPassword = localStorage.getItem('remembered_password')

  if (savedEmail) {
    form.value.email = savedEmail
    rememberAccount.value = true
  }

  if (savedPassword) {
    try {
      const decryptedPass = decrypt(savedPassword)
      if (decryptedPass) {
        form.value.password = decryptedPass
      }
    } catch (e) {
      console.error('Failed to decrypt saved password', e)
      localStorage.removeItem('remembered_password')
    }
  }
})

const clearError = (field: keyof typeof errors.value) => {
  errors.value[field] = ''
}

const handleLogin = () => {
  // Reset errors
  errors.value.email = ''
  errors.value.password = ''

  let hasError = false

  if (!form.value.email) {
    errors.value.email = t('auth.email_required')
    hasError = true
  } else if (!validateEmail(form.value.email)) {
    errors.value.email = t('auth.invalid_email_format')
    hasError = true
  }

  if (!form.value.password) {
    errors.value.password = t('auth.password_required')
    hasError = true
  } else if (!validatePassword(form.value.password)) {
    errors.value.password = t('auth.invalid_password_format')
    hasError = true
  }
  
  if (hasError) return

  const encryptedPassword = encrypt(form.value.password)

  // 调用登录接口
  login({
    email: form.value.email,
    password: encryptedPassword
  })
  .then((res) => {
    console.log('Login success:', res)
    // Store token and user info via store
    if (res.data?.token) {
      if (rememberAccount.value) {
        localStorage.setItem('remembered_account', form.value.email)
        // Encrypt password before saving to local storage for auto-fill
        // Note: Storing password in local storage has security risks, but requested by user
        localStorage.setItem('remembered_password', encryptedPassword)
      } else {
        localStorage.removeItem('remembered_account')
        localStorage.removeItem('remembered_password')
      }
      userStore.login(res.data)
      showToast(t('auth.login_success'), 'success')
      router.push('/workflows')
    }
  })
  .catch((error: any) => {
    console.error('Login error:', error)
  })
}

const goToRegister = () => {
  router.push('/register')
}
</script>

<template>
  <AuthLayout :title="t('auth.login_title')">
    <form @submit.prevent="handleLogin" class="auth-form" novalidate>
      <div class="form-group">
        <label>{{ t('auth.email_label') }}</label>
        <input 
          v-model="form.email" 
          type="email" 
          autocomplete="username"
          :placeholder="t('auth.email_placeholder')" 
          :class="{ 'error': errors.email }"
          @input="clearError('email')"
          @keyup.enter="handleLogin"
        >
        <div class="error-msg" v-if="errors.email">{{ errors.email }}</div>
      </div>
      
      <div class="form-group">
        <label>{{ t('auth.password_label') }}</label>
        <input 
          v-model="form.password" 
          type="password" 
          autocomplete="current-password"
          :placeholder="t('auth.password_placeholder')" 
          :class="{ 'error': errors.password }"
          @input="clearError('password')"
          @keyup.enter="handleLogin"
        >
        <div class="error-msg" v-if="errors.password">{{ errors.password }}</div>
      </div>
      
      <div class="form-options">
        <label class="checkbox-label">
          <input type="checkbox" v-model="rememberAccount">
          <span class="checkmark"></span>
          {{ t('auth.remember_account') }}
        </label>
      </div>

      <button type="submit" class="btn-neon full-width">
        {{ t('auth.login_btn') }}
      </button>
    </form>

    <template #footer>
      <p class="switch-text">
        {{ t('auth.no_account') }} 
        <a @click.prevent="goToRegister" href="#">{{ t('auth.register_link') }}</a>
      </p>
    </template>
  </AuthLayout>
</template>

<style scoped>
/* All common styles have been moved to AuthLayout.vue */

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-secondary);
  user-select: none;
}

.checkbox-label input {
  display: none;
}

.checkmark {
  width: 16px;
  height: 16px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  background: rgba(255, 255, 255, 0.05);
}

.checkbox-label input:checked + .checkmark {
  background: #fff;
  border-color: #fff;
}

.checkbox-label input:checked + .checkmark::after {
  content: '✓';
  color: #000;
  font-size: 12px;
  font-weight: bold;
}
</style>
<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, removeToast } = useToast()
</script>

<template>
  <div class="toast-container">
    <TransitionGroup name="toast">
      <div 
        v-for="toast in toasts" 
        :key="toast.id" 
        class="toast-item"
        :class="toast.type"
      >
        <!-- Icons -->
        <div class="toast-icon">
          <!-- Success -->
          <svg v-if="toast.type === 'success'" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          
          <!-- Error -->
          <svg v-else-if="toast.type === 'error'" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
          
          <!-- Warning -->
          <svg v-else-if="toast.type === 'warning'" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          
          <!-- Info -->
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        </div>
        
        <div class="toast-content">
          <span class="toast-message">{{ toast.message }}</span>
        </div>

        <button class="toast-close" @click="removeToast(toast.id)">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
        
        <!-- Progress bar background effect could go here if desired -->
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none;
}

.toast-item {
  pointer-events: auto;
  min-width: 320px;
  max-width: 480px;
  padding: 14px 16px;
  
  /* Glassmorphism & Cyberpunk base */
  background: rgba(18, 18, 18, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  
  display: flex;
  align-items: flex-start;
  gap: 12px;
  
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.1), 
    0 2px 4px -1px rgba(0, 0, 0, 0.06),
    0 12px 24px rgba(0, 0, 0, 0.2);
    
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.toast-content {
  flex: 1;
  display: flex;
  align-items: center;
  min-height: 20px; /* Align with icon height */
}

.toast-message {
  font-family: var(--font-ui, sans-serif); /* Prefer UI font, fallback sans */
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
  color: var(--text-primary, #fff);
  letter-spacing: 0.2px;
}

.toast-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 20px;
  width: 20px;
  margin-top: 1px; /* Optical alignment with text line-height */
  flex-shrink: 0;
}

.toast-close {
  background: transparent;
  border: none;
  padding: 2px;
  margin: -2px -4px 0 0;
  color: var(--text-secondary, #888);
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  opacity: 0.6;
}

.toast-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary, #fff);
  opacity: 1;
}

/* --- Theme Variants --- */

/* Success: Neon Green */
.toast-item.success {
  background: linear-gradient(to right, rgba(0, 255, 65, 0.03), rgba(18, 18, 18, 0.9));
  border-left: 1px solid var(--accent-neon, #00ff41); /* Minimal left accent */
  border-top: 1px solid rgba(0, 255, 65, 0.2);
  border-bottom: 1px solid rgba(0, 255, 65, 0.1);
  border-right: 1px solid rgba(0, 255, 65, 0.1);
  
  box-shadow: 
    0 4px 20px rgba(0, 255, 65, 0.15),
    inset 0 0 20px rgba(0, 255, 65, 0.02);
}

.toast-item.success .toast-icon {
  color: var(--accent-neon, #00ff41);
  filter: drop-shadow(0 0 5px rgba(0, 255, 65, 0.4));
}

/* Error: Neon Red */
.toast-item.error {
  background: linear-gradient(to right, rgba(255, 0, 60, 0.03), rgba(18, 18, 18, 0.9));
  border-left: 1px solid #ff003c;
  border-top: 1px solid rgba(255, 0, 60, 0.2);
  border-bottom: 1px solid rgba(255, 0, 60, 0.1);
  border-right: 1px solid rgba(255, 0, 60, 0.1);
  
  box-shadow: 
    0 4px 20px rgba(255, 0, 60, 0.15),
    inset 0 0 20px rgba(255, 0, 60, 0.02);
}

.toast-item.error .toast-icon {
  color: #ff003c;
  filter: drop-shadow(0 0 5px rgba(255, 0, 60, 0.4));
}

/* Warning: Neon Yellow */
.toast-item.warning {
  border-left: 1px solid #ffcc00;
  background: linear-gradient(to right, rgba(255, 204, 0, 0.03), rgba(18, 18, 18, 0.9));
}

.toast-item.warning .toast-icon {
  color: #ffcc00;
  filter: drop-shadow(0 0 5px rgba(255, 204, 0, 0.4));
}

/* Info: Neon Cyan */
.toast-item.info {
  border-left: 1px solid #00f3ff;
  background: linear-gradient(to right, rgba(0, 243, 255, 0.03), rgba(18, 18, 18, 0.9));
}

.toast-item.info .toast-icon {
  color: #00f3ff;
  filter: drop-shadow(0 0 5px rgba(0, 243, 255, 0.4));
}

/* Animations */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); /* Spring-like ease */
}

.toast-enter-from {
  opacity: 0;
  transform: translateY(-24px) scale(0.95);
}

.toast-leave-to {
  opacity: 0;
  transform: translateY(-12px) scale(0.98);
  pointer-events: none;
}

/* Hover Effect */
.toast-item:hover {
  transform: translateY(2px);
}
</style>

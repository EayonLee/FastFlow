<script setup lang="ts">
import InteractiveGrid from '../landing/InteractiveGrid.vue'
import AmbientGlow from '../common/AmbientGlow.vue'
import GlobalHeader from '../common/GlobalHeader.vue'
import GlobalFooter from '../common/GlobalFooter.vue'

defineProps<{
  title: string
}>()
</script>

<template>
  <div class="auth-page">
    <InteractiveGrid />
    <AmbientGlow />
    <GlobalHeader transparent />

    <main class="auth-container">
      <div class="card-wrapper">
        <div class="brand-logo">
          <span class="logo-text-fast">FAST</span>
          <span class="logo-text-flow glitch" data-text="FLOW">FLOW</span>
        </div>
        <div class="auth-card">
          <div class="card-header">
            <h2 class="title">{{ title }}</h2>
          </div>
          
          <slot></slot>

          <div class="card-footer">
            <slot name="footer"></slot>
          </div>
        </div>
      </div>
    </main>
    
    <GlobalFooter />
  </div>
</template>

<style scoped>
.auth-page {
  width: 100vw;
  height: 100vh;
  background-color: #030303;
  color: var(--text-primary);
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

.auth-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  position: relative;
  z-index: 10;
  padding: 20px;
}

/* Minimalist Luxury Card Design */
.card-wrapper {
  position: relative;
  width: 100%;
  max-width: 440px;
  z-index: 1;
}

.auth-card {
  background: rgba(10, 10, 10, 0.6);
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  padding: 48px 40px;
  border-radius: 12px;
  position: relative;
  overflow: hidden;
  box-shadow: 
    0 0 0 1px rgba(255, 255, 255, 0.08),
    0 20px 40px rgba(0, 0, 0, 0.4);
}

.card-header {
  margin-bottom: 32px;
  text-align: center;
  position: relative;
}

.brand-logo {
  text-align: center;
  margin-bottom: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
}

.logo-text-fast {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 42px;
  color: #fff;
  letter-spacing: -2px;
}

.logo-text-flow {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 42px;
  color: #00ff41;
  letter-spacing: -2px;
  position: relative;
}

/* Glitch Effect */
.glitch {
  position: relative;
  color: #00ff41;
  display: inline-block; /* Ensure width wraps content */
}

.glitch::before,
.glitch::after {
  content: attr(data-text);
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: transparent;
}

.glitch::before {
  left: 2px;
  text-shadow: -1px 0 #fff;
  clip: rect(24px, 550px, 90px, 0);
  animation: glitch-anim-2 3s infinite linear alternate-reverse;
}

.glitch::after {
  left: -2px;
  text-shadow: -1px 0 #fff;
  clip: rect(85px, 550px, 140px, 0);
  animation: glitch-anim 2.5s infinite linear alternate-reverse;
}

@keyframes glitch-anim {
  0% { clip: rect(17px, 9999px, 94px, 0); }
  20% { clip: rect(63px, 9999px, 5px, 0); }
  40% { clip: rect(16px, 9999px, 28px, 0); }
  60% { clip: rect(98px, 9999px, 57px, 0); }
  80% { clip: rect(59px, 9999px, 73px, 0); }
  100% { clip: rect(31px, 9999px, 94px, 0); }
}

@keyframes glitch-anim-2 {
  0% { clip: rect(129px, 9999px, 36px, 0); }
  20% { clip: rect(36px, 9999px, 4px, 0); }
  40% { clip: rect(138px, 9999px, 128px, 0); }
  60% { clip: rect(13px, 9999px, 7px, 0); }
  80% { clip: rect(74px, 9999px, 52px, 0); }
  100% { clip: rect(117px, 9999px, 10px, 0); }
}

/* Clean Title */
.title {
  font-family: var(--font-sans);
  color: #fff;
  font-size: 24px;
  letter-spacing: -0.5px;
  margin: 0;
  font-weight: 600;
}

.card-footer {
  margin-top: 32px;
  text-align: center;
  position: relative;
}

/* Deep selectors for form elements */
:deep(.auth-form) {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

:deep(.form-group) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:deep(label) {
  font-family: var(--font-sans);
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
  margin-left: 0;
  transition: color 0.2s;
}

:deep(.form-group:focus-within label) {
  color: #fff;
  text-shadow: none;
}

:deep(input) {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 12px 16px;
  color: #fff;
  font-family: var(--font-sans);
  font-size: 14px;
  transition: all 0.2s ease;
  width: 100%;
  box-sizing: border-box;
  height: 44px;
}

:deep(input:focus) {
  outline: none;
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.3);
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.05);
  transform: none;
}

:deep(input.error) {
  border-color: rgba(255, 70, 70, 0.5);
  background: rgba(255, 70, 70, 0.05);
  box-shadow: none;
  animation: shake 0.4s cubic-bezier(.36,.07,.19,.97) both;
}

/* Minimalist Button */
:deep(.btn-neon) {
  height: 44px;
  background: #fff;
  border: none;
  color: #000;
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0;
  position: relative;
  overflow: hidden;
  transition: all 0.2s ease;
  clip-path: none;
  border-radius: 6px;
  cursor: pointer;
  text-transform: none;
}

:deep(.btn-neon:hover) {
  background: #f0f0f0;
  color: #000;
  box-shadow: 0 0 20px rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

:deep(.btn-neon:active) {
  transform: translateY(0);
  background: #e0e0e0;
}

@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
  40%, 60% { transform: translate3d(4px, 0, 0); }
}

:deep(.error-msg) {
  color: #ff4d4f;
  font-size: 12px;
  margin-top: 6px;
  font-family: var(--font-sans);
  text-shadow: none;
  padding-left: 0;
}

:deep(.switch-text) {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.4);
  font-family: var(--font-sans);
}

:deep(.switch-text a) {
  color: #fff;
  text-decoration: none;
  margin-left: 6px;
  cursor: pointer;
  position: relative;
  font-weight: 500;
  transition: opacity 0.2s;
}

:deep(.switch-text a:hover) {
  opacity: 0.8;
}

:deep(.switch-text a::after) {
  display: none;
}

</style>
<script setup>
import { ref } from 'vue'
import NeonButton from '@/components/NeonButton.vue'

const emit = defineEmits(['navigate'])

const goToLogin = () => {
  emit('navigate', 'login')
}
</script>

<template>
  <div class="landing-view">
    <div class="hero-section">
      <h1 class="hero-title">
        <span class="title-main">Vibe Workflow</span>
        <span class="title-sub">Copilot</span>
      </h1>
      
      <p class="hero-desc">
        😎 FastFlow helps non-technical creators
        <br>
        <span class="sub-desc">automate tasks with AI</span>
      </p>
      
      <div class="cta-group">
        <NeonButton large @click="goToLogin">登录</NeonButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.landing-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 20px;
  position: relative;
  overflow: hidden;
}

.hero-title {
  font-family: var(--font-mono);
  font-size: 32px;
  margin-bottom: 24px;
  line-height: 1.1;
  letter-spacing: -0.5px;
}

.title-main {
  color: #fff;
  display: block;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.title-sub {
  color: var(--accent-neon);
  font-size: 32px;
  display: block;
  font-weight: 300;
  text-transform: uppercase;
  letter-spacing: 4px;
  text-shadow: 0 0 10px rgba(0, 255, 65, 0.3);
}

.hero-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 40px;
  line-height: 1.6;
  font-weight: 400;
}

.sub-desc {
  font-size: 14px;
  color: #fff;
  font-weight: 500;
}
</style>

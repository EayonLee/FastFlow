<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ref, onMounted, onBeforeUnmount } from 'vue'
import InteractiveGrid from '../components/landing/InteractiveGrid.vue'
import AmbientGlow from '../components/common/AmbientGlow.vue'
import GlobalHeader from '../components/common/GlobalHeader.vue'
import GlobalFooter from '../components/common/GlobalFooter.vue'

const router = useRouter()
const { t } = useI18n()

const mouseX = ref(0)
const mouseY = ref(0)
const windowWidth = ref(window.innerWidth)
const windowHeight = ref(window.innerHeight)

const goToWorkflows = () => {
  router.push('/workflows')
}

const handleMouseMove = (e: MouseEvent) => {
  mouseX.value = e.clientX
  mouseY.value = e.clientY
}

const handleResize = () => {
  windowWidth.value = window.innerWidth
  windowHeight.value = window.innerHeight
}

onMounted(() => {
  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', handleMouseMove)
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="landing-page">
    <InteractiveGrid />
    <AmbientGlow />
    
    <GlobalHeader transparent />

    <main class="hero-section">
      <div class="hero-content">
        <h1 class="hero-title">
          <span class="title-main">{{ t('landing.title') }}</span>
          <span class="title-sub glitch" :data-text="t('landing.subtitle')">{{ t('landing.subtitle') }}</span>
        </h1>
        <p class="hero-tagline">{{ t('landing.tagline') }}</p>
        <p class="hero-desc">{{ t('landing.description') }}</p>
        
        <div class="cta-group">
          <button class="btn-neon large" @click="goToWorkflows">{{ t('landing.cta') }}</button>
        </div>
      </div>
      
      <div class="hero-visual">
        <!-- Abstract Flow Visual -->
        <div class="flow-anim">
          <div class="node n1">
            <span class="icon">☕️</span>
            <span class="label">Coffee In</span>
            <div class="ripple-effect"></div>
          </div>
          <div class="node n2">
            <span class="icon">🧙‍♂️</span>
            <span class="label">Magic Box</span>
            <div class="ripple-effect"></div>
          </div>
          <div class="node n3">
            <span class="icon">🚀</span>
            <span class="label">Ship It!</span>
            <div class="ripple-effect"></div>
          </div>
          <svg class="lines" viewBox="0 0 100 100" preserveAspectRatio="none">
            <defs>
              <linearGradient id="line-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="var(--accent-neon)" stop-opacity="0" />
                <stop offset="50%" stop-color="var(--accent-neon)" stop-opacity="0.5" />
                <stop offset="100%" stop-color="#fff" stop-opacity="1" />
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            <!-- Path 1: Coffee In -> Magic Box -->
            <path d="M15 23 C 25 23, 35 43, 45 43" class="line-path" vector-effect="non-scaling-stroke" />
            <path d="M15 23 C 25 23, 35 43, 45 43" class="energy-pulse pulse-1" vector-effect="non-scaling-stroke" />
            
            <!-- Path 2: Magic Box -> Ship It -->
            <path d="M45 43 C 55 43, 65 33, 75 33" class="line-path" vector-effect="non-scaling-stroke" />
            <path d="M45 43 C 55 43, 65 33, 75 33" class="energy-pulse pulse-2" vector-effect="non-scaling-stroke" />
          </svg>
        </div>
      </div>
      
      <!-- HUD Elements -->
      <!-- Removed per user request -->
    </main>

    <GlobalFooter />
  </div>
</template>

<style scoped>
.landing-page {
  width: 100vw;
  height: 100vh;
  background-color: var(--bg-app);
  color: var(--text-primary);
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

.landing-nav, .hero-section, .landing-footer {
  position: relative;
  z-index: 10;
}

.hero-section {
  flex: 1;
  display: flex;
  align-items: center;
  padding: 0 10%;
  position: relative;
  width: 100%;
  box-sizing: border-box;
}

.neon {
  color: var(--accent-neon);
  text-shadow: 0 0 10px var(--accent-neon-dim);
}

/* .neon-flicker is now in global style.css */

.hud-top-left {
  position: absolute;
  top: 100px;
  left: 48px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-secondary);
  letter-spacing: 2px;
  opacity: 0.5;
  writing-mode: vertical-rl;
  transform: rotate(180deg);
}

.hud-bottom-right {
  position: absolute;
  bottom: 40px;
  right: 48px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-secondary);
  text-align: right;
  opacity: 0.7;
}

.hud-row {
  margin-bottom: 4px;
}

.neon-text {
  color: var(--accent-neon);
}

.author {
  color: var(--accent-neon);
  opacity: 0.8;
  text-decoration: none;
  transition: opacity 0.2s;
}

.author:hover {
  opacity: 1;
  text-decoration: underline;
}

.hero-content {
  z-index: 5;
  max-width: 600px;
}

.hero-title {
  font-family: var(--font-mono);
  font-size: 80px;
  line-height: 0.9;
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
}

.title-sub {
  margin-left: 60px;
  color: #00ff41;
  position: relative;
  min-height: 0.9em; /* Reserve space for text */
  display: block;
  width: fit-content;
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

.hero-tagline {
  font-size: 24px;
  color: var(--text-primary);
  margin-bottom: 16px;
  font-weight: 300;
}

.hero-desc {
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: 40px;
  line-height: 1.6;
  max-width: 480px;
}

.btn-neon.large {
  font-size: 16px;
  padding: 12px 32px;
  border-width: 2px;
}

/* Visuals */
.hero-visual {
  position: absolute;
  top: 0;
  right: 0;
  width: 60%;
  height: 100%;
  opacity: 0.8; /* Increased opacity */
  pointer-events: none;
}

.flow-anim {
  position: relative;
  width: 100%;
  height: 100%;
}

.node {
  position: absolute;
  width: 140px; /* Wider */
  height: 60px;
  border: 1px solid var(--accent-neon);
  background: rgba(5, 5, 5, 0.8); /* Darker background */
  backdrop-filter: blur(4px);
  border-radius: 8px;
  box-shadow: 0 0 15px rgba(0, 255, 65, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-family: var(--font-mono);
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  z-index: 2;
  transition: all 0.3s ease;
  padding: 0 16px;
  box-sizing: border-box;
  overflow: hidden; /* For ripple effect */
}

.node:hover {
  box-shadow: 0 0 25px rgba(0, 255, 65, 0.4);
  transform: scale(1.05);
  border-color: #fff;
}

.ripple-effect {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 0;
  height: 0;
  border-radius: 50%;
  background: rgba(0, 255, 65, 0.2);
  pointer-events: none;
  z-index: 0;
}

.icon {
  font-size: 18px;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.label {
  white-space: nowrap;
  position: relative;
  z-index: 1;
}

/* Animations */
.n1 { 
  top: 20%; 
  left: 10%; 
  animation: nodeFloat 6s ease-in-out infinite, nodeActivate 4s infinite; 
}
.n2 { 
  top: 40%; 
  left: 40%; 
  animation: nodeFloat 6s ease-in-out infinite 1s, nodeActivate 4s infinite 1.5s; 
}
.n3 { 
  top: 30%; 
  left: 70%; 
  animation: nodeFloat 6s ease-in-out infinite 2s, nodeActivate 4s infinite 3s; 
}

/* Specific ripple timing */
.n1 .ripple-effect { animation: ripple 4s infinite; }
.n2 .ripple-effect { animation: ripple 4s infinite 1.5s; }
.n3 .ripple-effect { animation: ripple 4s infinite 3s; }

.lines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
  filter: url(#glow);
}

.line-path {
  fill: none;
  stroke: rgba(255, 255, 255, 0.1);
  stroke-width: 1px;
}

.energy-pulse {
  fill: none;
  stroke: url(#line-gradient);
  stroke-width: 3px;
  stroke-dasharray: 100 1000;
  stroke-dashoffset: 200;
  stroke-linecap: round;
  animation: pulseMove 4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  opacity: 0;
}

@keyframes nodeFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

@keyframes pulseMove {
  0% { stroke-dashoffset: 200; opacity: 0; }
  10% { opacity: 1; }
  80% { stroke-dashoffset: -300; opacity: 1; }
  100% { stroke-dashoffset: -300; opacity: 0; }
}

@keyframes nodeActivate {
  0%, 10% { border-color: var(--accent-neon); box-shadow: 0 0 20px rgba(0, 255, 65, 0.4); color: #fff; }
  20% { border-color: var(--accent-neon); box-shadow: 0 0 10px rgba(0, 255, 65, 0.2); color: var(--text-primary); }
  100% { border-color: var(--accent-neon); box-shadow: 0 0 15px rgba(0, 255, 65, 0.2); } /* Keep subtle glow */
}

@keyframes ripple {
  0% { width: 0; height: 0; opacity: 0.8; }
  100% { width: 300px; height: 300px; opacity: 0; }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-20px); }
}

@keyframes pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
  100% { opacity: 1; transform: scale(1); }
}

@keyframes dash {
  to { stroke-dashoffset: -1000; }
}
</style>

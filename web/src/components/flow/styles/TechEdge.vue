<script setup lang="ts">
import { computed } from 'vue'
import { getBezierPath, type EdgeProps } from '@vue-flow/core'

const props = defineProps<EdgeProps>()

const path = computed(() => getBezierPath(props))
</script>

<template>
  <g class="tech-edge">
    <!-- Outer Glow (Static) -->
    <path 
      :d="path[0]" 
      fill="none" 
      stroke="var(--accent-neon)" 
      stroke-width="6" 
      stroke-opacity="0.15" 
      class="edge-glow"
    />

    <!-- Core Line (Static) -->
    <path 
      :d="path[0]" 
      fill="none" 
      stroke="var(--accent-neon)" 
      stroke-width="1.5" 
      class="edge-path"
    />

    <!-- Energy Particle (Animated) -->
    <circle r="3" fill="#ffffff">
      <animateMotion 
        dur="2s" 
        repeatCount="indefinite" 
        :path="path[0]"
        calcMode="linear"
      />
      <!-- Particle Glow -->
      <animate 
        attributeName="opacity" 
        values="0;1;0" 
        dur="2s" 
        repeatCount="indefinite" 
      />
    </circle>
  </g>
</template>

<style scoped>
.tech-edge {
  pointer-events: none;
}

.edge-path {
  stroke-dasharray: 10;
  animation: dash 30s linear infinite;
}

@keyframes dash {
  from {
    stroke-dashoffset: 1000;
  }
  to {
    stroke-dashoffset: 0;
  }
}
</style>

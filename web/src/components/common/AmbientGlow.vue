<script setup lang="ts">
// Ambient glow effect for page backgrounds
</script>

<template>
  <div class="bg-decorations">
    <div class="mesh-gradient">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
      <div class="blob blob-4"></div>
    </div>
    <div class="noise-overlay"></div>
  </div>
</template>

<style scoped>
.bg-decorations {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
  background-color: #050505; /* Deep dark base, not pure black */
}

.mesh-gradient {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  filter: blur(100px); /* Heavy blur for mesh effect */
  opacity: 0.4; /* Subtle blending */
}

.blob {
  position: absolute;
  border-radius: 50%;
  animation: float-mesh 20s infinite ease-in-out alternate;
}

/* Green/Emerald - Primary Brand */
.blob-1 {
  top: -10%;
  left: -10%;
  width: 50vw;
  height: 50vw;
  background: #00ff41;
  opacity: 0.4;
  animation-duration: 25s;
}

/* Deep Blue/Indigo - Depth */
.blob-2 {
  bottom: -10%;
  right: -10%;
  width: 60vw;
  height: 60vw;
  background: #4338ca;
  opacity: 0.3;
  animation-duration: 30s;
  animation-direction: alternate-reverse;
}

/* Cyan/Teal - Highlight */
.blob-3 {
  top: 40%;
  left: 40%;
  width: 40vw;
  height: 40vw;
  background: #06b6d4;
  opacity: 0.2;
  animation-duration: 22s;
  animation-delay: -5s;
}

/* Purple/Violet - Mystery */
.blob-4 {
  bottom: 20%;
  left: 10%;
  width: 35vw;
  height: 35vw;
  background: #7c3aed;
  opacity: 0.25;
  animation-duration: 28s;
  animation-delay: -10s;
}

.noise-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0.04;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
  pointer-events: none;
  mix-blend-mode: overlay;
}

@keyframes float-mesh {
  0% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -50px) scale(1.1); }
  66% { transform: translate(-20px, 20px) scale(0.9); }
  100% { transform: translate(0, 0) scale(1); }
}
</style>

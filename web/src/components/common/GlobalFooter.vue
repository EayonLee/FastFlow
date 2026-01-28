<script setup lang="ts">
import { computed } from 'vue'

const currentYear = computed(() => new Date().getFullYear())
</script>

<template>
  <footer class="global-footer">
    <div class="footer-content">
      <p class="copyright">© {{ currentYear }} FAST<span class="neon">FLOW</span></p>
      <p class="author">Created by <a href="mailto:lizhengtai@360.cn">lizhengtai@360.cn</a></p>
    </div>
  </footer>
</template>

<style scoped>
.global-footer {
  width: 100%;
  padding: 16px 24px;
  background: transparent;
  /* border-top: 1px solid var(--border-subtle);  Removed for transparent look */
  z-index: 10;
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: center;
  gap: 24px;
  align-items: center;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
}

.neon {
  color: var(--accent-neon);
  text-shadow: 0 0 5px var(--accent-neon-dim);
}

.author a {
  color: var(--accent-neon);
  text-decoration: none;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.author a:hover {
  opacity: 1;
  text-decoration: underline;
}
</style>

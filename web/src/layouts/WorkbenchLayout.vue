<script setup lang="ts">
import GlobalHeader from '../components/common/GlobalHeader.vue'
</script>

<template>
  <div class="workbench-layout">
    <GlobalHeader>
      <template #extra>
        <div class="header-extra">
          <slot name="header-extra"></slot>
        </div>
      </template>
    </GlobalHeader>
    
    <div class="workspace">
      <aside class="sidebar left" v-if="$slots['sidebar-left']">
        <div class="panel-title">MY WORKFLOWS</div>
        <slot name="sidebar-left"></slot>
      </aside>
      
      <main class="canvas-area">
        <slot></slot>
      </main>
      
      <aside class="sidebar right" v-if="$slots['sidebar-right']">
        <div class="panel-title">PROPERTIES</div>
        <slot name="sidebar-right"></slot>
      </aside>
    </div>

    <!-- GlobalFooter removed for workbench layout as requested -->
  </div>
</template>

<style scoped>
.workbench-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  background-color: var(--bg-app);
  --header-height: 64px; /* Increased height */
}

.workbench-footer {
  border-top: 1px solid var(--border-subtle);
  padding: 8px 24px; /* Smaller padding for workbench */
  font-size: 10px;
  background: var(--bg-panel);
}

.header-extra {
  display: flex;
  align-items: center;
  flex: 1;
}

.workspace {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.sidebar {
  width: var(--sidebar-width);
  background: var(--bg-panel);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  z-index: 5;
}

.sidebar.right {
  border-right: none;
  border-left: 1px solid var(--border-subtle);
}

.panel-title {
  padding: 10px 15px;
  font-size: 10px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  border-bottom: 1px solid var(--border-subtle);
  letter-spacing: 1px;
}

.canvas-area {
  flex: 1;
  position: relative;
  background-color: var(--bg-app);
  overflow: hidden;
}
</style>

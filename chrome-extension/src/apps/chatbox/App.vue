<script setup>
import Chat from './views/Chat.vue'

/**
 * App 根组件
 * 作用：作为应用的入口容器，负责渲染具体的视图组件。
 */
</script>

<template>
  <div class="fastflow-wrapper">
    <!-- 渲染聊天视图 -->
    <Chat />
  </div>
</template>

<style scoped>
.fastflow-wrapper {
  /* 基础容器样式 */
  width: 100%;
  height: 100%;
}
</style>

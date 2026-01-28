import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { crx } from '@crxjs/vite-plugin'
import manifest from './manifest.json'

/**
 * Vite 配置文件
 * 作用：配置 Chrome 插件的构建流程。
 * 实现：
 * 1. 使用 @crxjs/vite-plugin 插件，这是目前业内标准的 Chrome 扩展开发方案。
 * 2. 它可以自动解析 manifest.json，处理 content scripts 和 background scripts 的 HMR (热重载)。
 * 3. 不再需要手动维护 timestamp.json 或手动注入脚本，CRXJS 会通过 WebSocket 自动更新。
 */
export default defineConfig({
  plugins: [
    vue(),
    // 使用 CRXJS 插件处理 Chrome 扩展构建和热重载
    crx({ manifest }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  // 生产环境构建配置
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // CRXJS 会自动处理 rollupOptions，通常不需要手动配置
  }
})

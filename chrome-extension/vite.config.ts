import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { crx } from '@crxjs/vite-plugin'
import manifest from './manifest.json'

export default defineConfig({
  // 必须使用相对 base，避免 Vite 产物在 content-script 中加载 chunk/css 时走到页面域名下（导致 MIME=text/html / 404）。
  // 例如：不应请求 http(s)://<page>/assets/*.js，而应始终从 chrome-extension://<id>/assets/*.js 加载。
  base: './',
  plugins: [
    vue(),
    crx({ manifest })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
})

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { crx } from '@crxjs/vite-plugin'
import { createManifest } from './manifest.config.js'
import { createSharedConfig } from './shared-config.js'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '')
  const sharedConfig = createSharedConfig(env)
  const isProdMode = mode === 'prod'

  return {
    // 必须使用相对 base，避免 Vite 产物在 content-script 中加载 chunk/css 时走到页面域名下（导致 MIME=text/html / 404）。
    // 例如：不应请求 http(s)://<page>/assets/*.js，而应始终从 chrome-extension://<id>/assets/*.js 加载。
    base: './',
    plugins: [
      vue(),
      crx({ manifest: createManifest(sharedConfig) })
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@config': path.resolve(__dirname, './src/config/runtime-config.js')
      }
    },
    build: {
      outDir: isProdMode ? 'dist-prod' : 'dist-dev',
      emptyOutDir: true
    }
  }
})

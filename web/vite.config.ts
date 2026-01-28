import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    envPrefix: ['VITE_', 'AUTH_'], // 允许以 AUTH_ 开头的环境变量暴露给客户端
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src')
      }
    },
    server: {
      proxy: {
        '/fastflow/api/v1': {
          target: env.VITE_API_BASE_URL,
          changeOrigin: true,
          // rewrite: (path) => path.replace(/^\/fastflow\/api\/v1/, '') // 如果后端不需要前缀则开启 rewrite
        },
        '/fastflow/nexus/v1': {
          target: env.VITE_NEXUS_URL,
          changeOrigin: true
        }
      }
    }
  }
})

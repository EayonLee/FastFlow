import '@/styles/base.css' // 引入基础样式
import '@/styles/variables.css' // 引入 CSS 变量
import '@/styles/components/header.css' // 引入 Header 样式
import { themeManager } from '@/utils/themeManager.js'
import { createApp } from 'vue'
import App from './App.vue'

const app = createApp(App)
app.mount('#app')

themeManager.ready.then(() => {
  themeManager.register(document.documentElement)
})

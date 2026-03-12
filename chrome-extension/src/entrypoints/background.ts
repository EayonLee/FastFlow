import { defineBackground } from 'wxt/utils/define-background'
import { initializeBackground } from '@/extension/background/service-worker.js'

export default defineBackground(() => {
  initializeBackground()
})

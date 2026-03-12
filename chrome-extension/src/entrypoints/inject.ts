import { defineUnlistedScript } from 'wxt/utils/define-unlisted-script'
import { initializeInjectBridge } from '@/extension/inject/index.js'

export default defineUnlistedScript(() => {
  initializeInjectBridge()
})

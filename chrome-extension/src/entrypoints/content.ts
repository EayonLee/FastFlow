import { defineContentScript } from 'wxt/utils/define-content-script'
import { bootstrapChatboxContentScript } from '@/extension/content/bootstrap.js'

export default defineContentScript({
  matches: ['<all_urls>'],
  allFrames: true,
  main() {
    bootstrapChatboxContentScript()
  }
})

import { CONFIG } from '@/config/index.js'

let isDetected = false

function check() {
  // 只要有选择器匹配即可
  return CONFIG.ELEMENT_SELECTORS.some((selector) => document.querySelector(selector))
}

function getEnvInfo() {
  return window.self === window.top ? 'Main Window' : 'Iframe'
}

export const Detector = {
  check,
  getEnvInfo,
  isDetected: () => isDetected,
  setDetected: (val) => {
    isDetected = val
  }
}

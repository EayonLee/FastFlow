/**
 * Chrome 插件唯一的共享配置工厂。
 *
 * 说明：
 * 1. manifest、service worker、页面侧运行时代码统一复用这一份配置生成逻辑。
 * 2. API / Nexus 地址必须通过构建环境注入，避免开发与发布地址写死在代码里。
 * 3. 其余静态配置仍集中定义在这里，防止出现第二份配置源。
 */

function normalizeBaseUrl(value, key) {
  const normalized = String(value || '').trim().replace(/\/+$/, '')
  if (!normalized) {
    throw new Error(`[shared-config] Missing required env: ${key}`)
  }
  return normalized
}

function normalizeRequiredValue(value, key) {
  const normalized = String(value || '').trim()
  if (!normalized) {
    throw new Error(`[shared-config] Missing required env: ${key}`)
  }
  return normalized
}

function normalizeExtensionVersion(value, key) {
  const normalized = normalizeRequiredValue(value, key)
  if (!/^\d+\.\d+\.\d+(?:\.\d+)?$/.test(normalized)) {
    throw new Error(`[shared-config] Invalid extension version "${normalized}" for ${key}. Chrome manifest version must use numeric dot segments only.`)
  }
  return normalized
}

export function createSharedConfig(env = {}) {
  const EXTENSION_VERSION = normalizeExtensionVersion(env.VITE_EXTENSION_VERSION, 'VITE_EXTENSION_VERSION')
  const EXTENSION_VERSION_NAME = normalizeRequiredValue(
    env.VITE_EXTENSION_VERSION_NAME || env.VITE_EXTENSION_VERSION,
    'VITE_EXTENSION_VERSION_NAME'
  )
  const API_BASE_URL = normalizeBaseUrl(env.VITE_API_BASE_URL, 'VITE_API_BASE_URL')
  const NEXUS_BASE_URL = normalizeBaseUrl(env.VITE_NEXUS_BASE_URL, 'VITE_NEXUS_BASE_URL')
  const HOST_PERMISSIONS = [
    `${API_BASE_URL}/*`,
    `${NEXUS_BASE_URL}/*`
  ]
  const PASSWORD_SECRET_KEY = 'd7b8a2c9e4f10536'
  const AUTH_CHECK_INTERVAL_MS = 60 * 1000
  const ELEMENT_SELECTORS = [
    '.vue-flow-wrapper',
    '.react-flow',
    '.react-flow__renderer',
    '.react-flow__pane',
    '[class*="react-flow"]',
    '[class*="vue-flow"]'
  ]

  return {
    EXTENSION_VERSION,
    EXTENSION_VERSION_NAME,
    API_BASE_URL,
    NEXUS_BASE_URL,
    HOST_PERMISSIONS,
    PASSWORD_SECRET_KEY,
    AUTH_CHECK_INTERVAL_MS,
    ELEMENT_SELECTORS
  }
}

import { DEV_EXTENSION_PUBLIC_KEY, PROD_EXTENSION_PUBLIC_KEY } from './keys'

export type ReleaseChannel = 'development' | 'production'

export interface ChannelConfig {
  apiBaseUrl: string
  nexusBaseUrl: string
  hostPermissions: string[]
  authCheckIntervalMs: number
  elementSelectors: string[]
  extensionPublicKey: string
}

export interface ChannelOverrides {
  apiBaseUrl?: string
  nexusBaseUrl?: string
}

const AUTH_CHECK_INTERVAL_MS = 60 * 1000
const ELEMENT_SELECTORS = [
  '.vue-flow-wrapper',
  '.react-flow',
  '.react-flow__renderer',
  '.react-flow__pane',
  '[class*="react-flow"]',
  '[class*="vue-flow"]'
]

const CHANNELS: Record<ReleaseChannel, Omit<ChannelConfig, 'hostPermissions'>> = {
  development: {
    apiBaseUrl: 'http://127.0.0.1:8080',
    nexusBaseUrl: 'http://127.0.0.1:9090',
    authCheckIntervalMs: AUTH_CHECK_INTERVAL_MS,
    elementSelectors: ELEMENT_SELECTORS,
    extensionPublicKey: DEV_EXTENSION_PUBLIC_KEY
  },
  production: {
    apiBaseUrl: 'http://11.120.80.177:8080',
    nexusBaseUrl: 'http://11.120.80.177:9090',
    authCheckIntervalMs: AUTH_CHECK_INTERVAL_MS,
    elementSelectors: ELEMENT_SELECTORS,
    extensionPublicKey: PROD_EXTENSION_PUBLIC_KEY
  }
}

function normalizeBaseUrl(value: string | undefined, fieldName: string): string {
  const normalized = String(value || '').trim().replace(/\/+$/, '')
  if (!normalized) {
    throw new Error(`[channels] Missing required value: ${fieldName}`)
  }
  return normalized
}

function buildHostPermissions(apiBaseUrl: string, nexusBaseUrl: string): string[] {
  return Array.from(new Set([`${apiBaseUrl}/*`, `${nexusBaseUrl}/*`]))
}

export function resolveReleaseChannel(mode?: string): ReleaseChannel {
  return mode === 'production' ? 'production' : 'development'
}

export function resolveChannelConfig(
  channel: ReleaseChannel,
  overrides: ChannelOverrides = {}
): ChannelConfig {
  const baseConfig = CHANNELS[channel]
  const apiBaseUrl = normalizeBaseUrl(overrides.apiBaseUrl ?? baseConfig.apiBaseUrl, `${channel}.apiBaseUrl`)
  const nexusBaseUrl = normalizeBaseUrl(
    overrides.nexusBaseUrl ?? baseConfig.nexusBaseUrl,
    `${channel}.nexusBaseUrl`
  )

  return {
    ...baseConfig,
    apiBaseUrl,
    nexusBaseUrl,
    hostPermissions: buildHostPermissions(apiBaseUrl, nexusBaseUrl)
  }
}

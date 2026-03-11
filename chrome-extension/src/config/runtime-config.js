import { createSharedConfig } from '../../shared-config.js'

export const CONFIG = createSharedConfig(import.meta.env)

export const {
  EXTENSION_VERSION,
  EXTENSION_VERSION_NAME,
  API_BASE_URL,
  NEXUS_BASE_URL,
  HOST_PERMISSIONS,
  PASSWORD_SECRET_KEY,
  AUTH_CHECK_INTERVAL_MS,
  ELEMENT_SELECTORS
} = CONFIG

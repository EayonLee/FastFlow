import type { BuildEnv } from './env'

import { readBuildChannelOverrides } from './env'
import { resolveChannelConfig, resolveReleaseChannel } from './channels'

const EXTENSION_ICONS = {
  16: '/logo.png',
  32: '/logo.png',
  48: '/logo.png',
  128: '/logo.png'
} as const

const BASE_PERMISSIONS = [
  'activeTab',
  'tabs',
  'scripting',
  'storage',
  'clipboardWrite',
  'clipboardRead'
] as const
const CONTENT_SCRIPT_MATCHES = ['<all_urls>'] as const
const INJECT_SCRIPT_RESOURCE = 'inject.js' as const

interface CreateManifestConfigOptions {
  mode?: string
  version: string
  env?: BuildEnv
}

export function createManifestConfig({ mode, version, env }: CreateManifestConfigOptions) {
  const releaseChannel = resolveReleaseChannel(mode)
  const channelConfig = resolveChannelConfig(
    releaseChannel,
    readBuildChannelOverrides(releaseChannel, env)
  )
  const isDevelopment = releaseChannel === 'development'

  return {
    name: isDevelopment ? 'FastFlow Copilot (Dev)' : 'FastFlow Copilot',
    description: 'FastFlow Vibe Workflow',
    key: channelConfig.extensionPublicKey,
    version_name: isDevelopment ? `${version}-dev` : version,
    permissions: [...BASE_PERMISSIONS],
    host_permissions: channelConfig.hostPermissions,
    icons: EXTENSION_ICONS,
    action: {
      default_icon: EXTENSION_ICONS
    },
    web_accessible_resources: [
      {
        resources: [INJECT_SCRIPT_RESOURCE],
        matches: [...CONTENT_SCRIPT_MATCHES]
      }
    ]
  }
}

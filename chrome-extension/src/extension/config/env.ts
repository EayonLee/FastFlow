import type { ChannelOverrides, ReleaseChannel } from './channels'

export interface BuildEnv extends NodeJS.ProcessEnv {
  MODE?: string
  WXT_API_BASE_URL?: string
  WXT_NEXUS_BASE_URL?: string
}

export interface RuntimeEnv extends ImportMetaEnv {
  WXT_API_BASE_URL?: string
  WXT_NEXUS_BASE_URL?: string
}

function readDevOverrides(env: Pick<BuildEnv, 'WXT_API_BASE_URL' | 'WXT_NEXUS_BASE_URL'>): ChannelOverrides {
  return {
    apiBaseUrl: env.WXT_API_BASE_URL,
    nexusBaseUrl: env.WXT_NEXUS_BASE_URL
  }
}

export function readBuildEnv(env: NodeJS.ProcessEnv = process.env): BuildEnv {
  return env
}

export function readRuntimeEnv(env: RuntimeEnv = import.meta.env): RuntimeEnv {
  return env
}

export function readBuildChannelOverrides(
  channel: ReleaseChannel,
  env: BuildEnv = readBuildEnv()
): ChannelOverrides {
  if (channel !== 'development') return {}
  return readDevOverrides(env)
}

export function readRuntimeChannelOverrides(
  channel: ReleaseChannel,
  env: RuntimeEnv = readRuntimeEnv()
): ChannelOverrides {
  if (channel !== 'development') return {}
  return readDevOverrides(env)
}

export function resolveRuntimeMode(env: RuntimeEnv = readRuntimeEnv()): string | undefined {
  return env.MODE
}

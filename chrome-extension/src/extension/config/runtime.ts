import { readRuntimeChannelOverrides, resolveRuntimeMode } from './env'
import { resolveChannelConfig, resolveReleaseChannel } from './channels'

export const releaseChannel = resolveReleaseChannel(resolveRuntimeMode())

export const runtimeConfig = Object.freeze(
  resolveChannelConfig(releaseChannel, readRuntimeChannelOverrides(releaseChannel))
)

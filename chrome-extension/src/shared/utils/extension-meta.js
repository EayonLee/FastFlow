function getManifest() {
  return globalThis.chrome?.runtime?.getManifest?.() || null
}

export function getExtensionVersionName() {
  const manifest = getManifest()
  return manifest?.version_name || manifest?.version || '0.0.0'
}

export function getExtensionDisplayVersion() {
  return `v${getExtensionVersionName()}`
}

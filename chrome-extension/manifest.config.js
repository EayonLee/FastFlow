export function createManifest(sharedConfig) {
  const manifest = {
    manifest_version: 3,
    name: 'FastFlow Copilot',
    version: sharedConfig.EXTENSION_VERSION,
    description: 'FastFlow Vibe Workflow',
    permissions: [
      'activeTab',
      'tabs',
      'scripting',
      'storage',
      'clipboardWrite',
      'clipboardRead'
    ],
    host_permissions: sharedConfig.HOST_PERMISSIONS,
    background: {
      service_worker: 'src/background/service-worker.js',
      type: 'module'
    },
    content_scripts: [
      {
        matches: ['<all_urls>'],
        js: [
          'src/chatbox/main.js'
        ],
        css: [],
        all_frames: true
      }
    ],
    web_accessible_resources: [
      {
        resources: [
          'assets/*',
          'src/inject/index.js',
          'src/utils/workflowGraph.js',
          'src/utils/workflowMeta.js'
        ],
        matches: ['<all_urls>']
      }
    ],
    icons: {
      '16': 'src/assets/logo/logo.png',
      '32': 'src/assets/logo/logo.png',
      '48': 'src/assets/logo/logo.png',
      '128': 'src/assets/logo/logo.png'
    },
    action: {
      default_popup: 'src/popup/popup.html',
      default_icon: {
        '16': 'src/assets/logo/logo.png',
        '32': 'src/assets/logo/logo.png',
        '48': 'src/assets/logo/logo.png',
        '128': 'src/assets/logo/logo.png'
      }
    }
  }

  if (sharedConfig.EXTENSION_VERSION_NAME !== sharedConfig.EXTENSION_VERSION) {
    manifest.version_name = sharedConfig.EXTENSION_VERSION_NAME
  }

  return manifest
}

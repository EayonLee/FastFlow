import { readFileSync } from 'node:fs'

import { defineConfig } from 'wxt'

import { sanitizeJsOutputPlugin } from './src/extension/config/build/sanitize-js-output'
import { createManifestConfig } from './src/extension/config/manifest'

const packageJson = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as {
  version?: string
}

const extensionVersion = packageJson.version || '0.0.0'

export default defineConfig({
  srcDir: 'src',
  publicDir: 'src/public',
  outDir: 'dist',
  outDirTemplate: '{{mode}}',
  browser: 'chrome',
  manifestVersion: 3,
  imports: false,
  modules: ['@wxt-dev/module-vue'],
  vite: () => ({
    build: {
      rollupOptions: {
        plugins: [sanitizeJsOutputPlugin()]
      }
    }
  }),
  manifest: ({ mode }) =>
    createManifestConfig({
      mode,
      version: extensionVersion,
      env: process.env
    })
})

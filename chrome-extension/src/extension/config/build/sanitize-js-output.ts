import { TextDecoder } from 'node:util'

import { minify } from 'terser'

import type { OutputAsset, OutputBundle, OutputChunk, Plugin } from 'rollup'

const ASCII_PRINTABLE_MAX = 0x7e
const ALLOWED_CONTROL_CODES = new Set([0x09, 0x0a, 0x0d])
const textDecoder = new TextDecoder('utf-8', { fatal: true })

interface JavaScriptEncodingViolation {
  codePoint: number
  column: number
  fileName: string
  line: number
}

function isDisallowedCodePoint(codePoint: number): boolean {
  return (codePoint < 0x20 && !ALLOWED_CONTROL_CODES.has(codePoint)) || codePoint > ASCII_PRINTABLE_MAX
}

function getLineColumn(source: string, index: number): { line: number; column: number } {
  let line = 1
  let column = 1

  for (let i = 0; i < index; i += 1) {
    if (source[i] === '\n') {
      line += 1
      column = 1
      continue
    }

    column += 1
  }

  return { line, column }
}

function findJavaScriptEncodingViolations(source: string, fileName: string): JavaScriptEncodingViolation[] {
  const violations: JavaScriptEncodingViolation[] = []

  for (let index = 0; index < source.length; index += 1) {
    const codePoint = source.charCodeAt(index)
    if (!isDisallowedCodePoint(codePoint)) continue

    const { line, column } = getLineColumn(source, index)
    violations.push({
      codePoint,
      column,
      fileName,
      line
    })
  }

  return violations
}

function formatViolation(violation: JavaScriptEncodingViolation): string {
  const hex = violation.codePoint.toString(16).toUpperCase().padStart(4, '0')
  return `${violation.fileName}:${violation.line}:${violation.column} U+${hex}`
}

function decodeAssetSource(fileName: string, source: OutputAsset['source']): string {
  if (typeof source === 'string') return source

  try {
    return textDecoder.decode(source)
  } catch (error) {
    throw new Error(
      `[sanitize-js-output] ${fileName} is not valid UTF-8 before sanitization: ${
        error instanceof Error ? error.message : 'unknown decode error'
      }`
    )
  }
}

async function sanitizeJavaScriptSource(fileName: string, source: string): Promise<string> {
  const result = await minify(source, {
    compress: false,
    mangle: false,
    format: {
      ascii_only: true,
      comments: false,
      semicolons: true
    }
  })

  if (!result.code) {
    throw new Error(`[sanitize-js-output] ${fileName} produced empty output during sanitization`)
  }

  const violations = findJavaScriptEncodingViolations(result.code, fileName)
  if (violations.length > 0) {
    const preview = violations.slice(0, 5).map(formatViolation).join(', ')
    throw new Error(
      `[sanitize-js-output] ${fileName} still contains disallowed characters after sanitization: ${preview}`
    )
  }

  return result.code
}

async function sanitizeChunk(chunk: OutputChunk): Promise<void> {
  chunk.code = await sanitizeJavaScriptSource(chunk.fileName, chunk.code)
}

async function sanitizeAsset(asset: OutputAsset): Promise<void> {
  asset.source = await sanitizeJavaScriptSource(asset.fileName, decodeAssetSource(asset.fileName, asset.source))
}

export function sanitizeJsOutputPlugin(): Plugin {
  return {
    name: 'sanitize-js-output',
    async generateBundle(_options, bundle: OutputBundle) {
      for (const output of Object.values(bundle)) {
        if (!output.fileName.endsWith('.js')) continue

        if (output.type === 'chunk') {
          await sanitizeChunk(output)
          continue
        }

        await sanitizeAsset(output)
      }
    }
  }
}

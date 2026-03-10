import { normalizeString } from './common.js'
import { skillProtocol } from './skillProtocol.js'
import { nodeProtocol } from './nodeProtocol.js'

/**
 * 协议注册表：
 * 后续新增协议只需新增一个协议模块并挂到这里。
 */
export const protocolRegistry = [skillProtocol, nodeProtocol]

const protocolMap = new Map(protocolRegistry.map((protocol) => [protocol.mode, protocol]))

export function getProtocolByMode(mode) {
  const normalizedMode = normalizeString(mode)
  return protocolMap.get(normalizedMode) || protocolRegistry[0]
}

export function detectProtocolByTextBeforeCursor(textBeforeCursor) {
  const sourceText = String(textBeforeCursor || '')

  // 按注册顺序检测 trigger，命中即返回。
  for (const protocol of protocolRegistry) {
    const match = sourceText.match(protocol.triggerRegex)
    if (!match) continue

    const query = normalizeString(match[2]).toLowerCase()
    return {
      protocol,
      query,
      tokenLength: query.length + 1,
    }
  }

  return null
}

export const protocolTokenNodes = protocolRegistry.map((protocol) => protocol.tokenNode)

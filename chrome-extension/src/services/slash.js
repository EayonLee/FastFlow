import { authService } from '@/services/auth.js'
import { CONFIG } from '@/config/index.js'

/**
 * 读取 Slash 目录（skills + mcp 占位）的服务模块。
 *
 * 说明：
 * - 此模块只负责“slash 非流式目录接口”，与 `nexus.js` 的 agent 流式能力解耦。
 * - 前端调用 API 模块地址，再由 API 代理到 Nexus，避免浏览器侧跨服务直连。
 */

/**
 * 请求 API 模块的 slash 目录接口并返回目录数据。
 *
 * 调用链路：
 * chrome-extension -> API(`/fastflow/api/v1/clash/catalog`) -> Nexus(`/fastflow/nexus/v1/slash/catalog`)
 *
 * @returns {Promise<{skills: Array, mcp: Array}>}
 */
async function getSlashCatalog() {
  // Authorization 由登录模块统一维护，这里只做透传。
  const token = await authService.getToken() || ''
  const response = await fetch(`${CONFIG.API_BASE_URL}/fastflow/api/v1/clash/catalog`, {
    method: 'GET',
    headers: { 'Authorization': token }
  })

  // 只解析一次响应体，避免 “body stream already read” 错误。
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.message || `Request failed with status ${response.status}`)
  }
  if (!payload || payload.code !== 200) {
    throw new Error(payload?.message || 'get slash catalog failed')
  }

  // 统一返回目录结构，调用方只关心 data 层业务字段。
  return payload.data || { skills: [], mcp: [] }
}

export const Slash = {
  getSlashCatalog
}

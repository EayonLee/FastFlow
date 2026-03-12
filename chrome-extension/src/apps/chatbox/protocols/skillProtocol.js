import { Slash } from '@/shared/services/slash.js'
import { createProtocolTokenNode, createTriggerRegex, normalizeString } from './common.js'

/**
 * Skill 协议定义：
 * - trigger: /
 * - token: selected_skill(<skill_name>)
 * - 数据源: /clash/catalog 返回的 skills
 */
const MODE = 'skill'
const TOKEN_NODE_NAME = 'protocolSkillToken'

const tokenNode = createProtocolTokenNode({
  nodeName: TOKEN_NODE_NAME,
  dataAttr: 'data-protocol-skill-token',
  cssClass: 'composer-skill-chip',
  attrs: {
    name: {
      default: '',
    },
  },
  getLabel: (attrs) => String(attrs.name || ''),
  serializeText: (attrs) => `selected_skill(${String(attrs.name || '')})`,
})

function mapSkillOption(rawItem) {
  const skillName = normalizeString(rawItem?.skill_name)
  if (!skillName) return null

  return {
    key: skillName,
    leftLabel: skillName,
    rightLabel: normalizeString(rawItem?.description) || '-',
    rightClass: '',
    rightTitle: normalizeString(rawItem?.description),
    disabled: rawItem?.enabled === false,
    payload: rawItem,
  }
}

function filterSkillOption(option, query) {
  const normalizedQuery = normalizeString(query).toLowerCase()
  if (!normalizedQuery) return true

  const skillName = normalizeString(option?.payload?.skill_name).toLowerCase()
  const title = normalizeString(option?.payload?.name).toLowerCase()
  const description = normalizeString(option?.payload?.description).toLowerCase()
  return skillName.includes(normalizedQuery)
    || title.includes(normalizedQuery)
    || description.includes(normalizedQuery)
}

async function loadSkillItems() {
  const catalog = await Slash.getSlashCatalog()
  return Array.isArray(catalog?.skills) ? catalog.skills : []
}

// 注册到协议内核的 skill 实现。
export const skillProtocol = {
  mode: MODE,
  triggerChar: '/',
  triggerRegex: createTriggerRegex('/', '[a-z0-9-]*', 'i'),
  reloadOnOpen: false,
  tokenNodeName: TOKEN_NODE_NAME,
  tokenNode,
  panel: {
    title: 'SKILLS',
    badge: 'Available',
    loadingText: '加载中...',
    emptyText: '没有可选 skill',
    hintText: '可直接在输入框输入 / 快速唤起',
    sectionClass: 'skills-section',
  },
  secondarySection: {
    title: 'MCP',
    badge: 'Coming Soon',
    sectionClass: 'mcp-section',
    placeholderText: '开发中...',
  },
  async loadItems() {
    return await loadSkillItems()
  },
  toOption(rawItem) {
    return mapSkillOption(rawItem)
  },
  filterOption(option, query) {
    return filterSkillOption(option, query)
  },
  isSelectable(option) {
    return option?.disabled !== true
  },
  toInsertAttrs(option) {
    const skillName = normalizeString(option?.payload?.skill_name)
    return { name: skillName }
  },
}

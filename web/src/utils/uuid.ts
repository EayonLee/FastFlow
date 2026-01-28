/**
 * UUID 生成工具
 * 用于生成不带横杠的 32 位 UUID
 */
import { customAlphabet } from 'nanoid'

// 自定义 nanoid：32位，仅包含数字和小写字母
const nanoid = customAlphabet('0123456789abcdefghijklmnopqrstuvwxyz', 32)

/**
 * 生成 32 位无横杠 UUID
 * @returns {string} 32位随机字符串
 */
export const generateUUID = (): string => {
  return nanoid()
}

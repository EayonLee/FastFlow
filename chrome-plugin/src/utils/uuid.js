// 生成 32 位 UUID（无连字符）
export function generateUuid32() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, '')
  }

  // 兼容：使用 getRandomValues 生成 16 字节，再转为 32 位 hex
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const bytes = new Uint8Array(16)
    crypto.getRandomValues(bytes)
    return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  }

  // 兜底：时间戳 + 随机数拼接（仍保证 32 位）
  const timeHex = Date.now().toString(16).padStart(12, '0')
  const randHex = Math.floor(Math.random() * 0xffffffffffff)
    .toString(16)
    .padStart(12, '0')
  return (timeHex + randHex).padEnd(32, '0').slice(0, 32)
}

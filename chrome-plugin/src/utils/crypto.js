import CryptoJS from 'crypto-js'

// 16位 AES 密钥，必须与后端保持一致
const KEY_STR = import.meta.env.AUTH_PASSWORD_SECRET_KEY || ''
if (!KEY_STR) {
  console.warn('AUTH_PASSWORD_SECRET_KEY is missing in environment variables!')
}
const KEY = CryptoJS.enc.Utf8.parse(KEY_STR)

/**
 * AES 加密
 * @param word 待加密字符串
 * @returns 加密后的 Base64 字符串
 */
export const encrypt = (word) => {
  if (!word) return ''
  const srcs = CryptoJS.enc.Utf8.parse(word)
  const encrypted = CryptoJS.AES.encrypt(srcs, KEY, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7
  })
  return encrypted.toString()
}

/**
 * AES 解密 (预留)
 * @param word 待解密字符串
 * @returns 解密后的字符串
 */
export const decrypt = (word) => {
  if (!word) return ''
  const bytes = CryptoJS.AES.decrypt(word, KEY, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7
  })
  return bytes.toString(CryptoJS.enc.Utf8)
}

import CryptoJS from 'crypto-js'
import { AUTH_PASSWORD_AES_KEY } from '@/extension/protocol/auth-protocol.js'

const KEY = CryptoJS.enc.Utf8.parse(AUTH_PASSWORD_AES_KEY)

/**
 * AES 加密
 * @param word 待加密字符串
 * @returns 加密后的 Base64 字符串
 */
export function encrypt(word) {
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
export function decrypt(word) {
  if (!word) return ''
  const bytes = CryptoJS.AES.decrypt(word, KEY, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7
  })
  return bytes.toString(CryptoJS.enc.Utf8)
}

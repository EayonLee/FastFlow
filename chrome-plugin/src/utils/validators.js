/**
 * 统一校验工具函数文件
 * 包含项目中通用的表单校验逻辑
 */

/**
 * 校验用户名
 * 规则：长度大于5位，支持英文、数字和_，不能以数字和_开头，必须以英文开头
 * @param name 用户名
 */
export function validateName(name) {
  return /^[a-zA-Z][a-zA-Z0-9_]{4,}$/.test(name)
}

/**
 * 校验邮箱
 * 规则：必须是 @360.cn 结尾的企业邮箱
 * @param email 邮箱地址
 */
export function validateEmail(email) {
  const emailRegex = /^[a-zA-Z0-9._%+-]+@360\.cn$/
  return emailRegex.test(email)
}

/**
 * 校验密码
 * 规则：8-22位字符，必须包含至少一个字母和一个数字
 * @param password 密码
 */
export function validatePassword(password) {
  const passwordRegex = /^(?=.*[A-Za-z])(?=.*\d).{8,22}$/
  return passwordRegex.test(password)
}

/**
 * 校验验证码
 * 规则：4位数字
 * @param code 验证码
 */
export function validateCode(code) {
  return /^\d{4}$/.test(code)
}

const USERNAME_REGEX = /^[A-Za-z0-9\u4e00-\u9fa5]{5,12}$/
const EMAIL_360_REGEX = /^[a-zA-Z0-9._%+-]+@360\.cn$/
const INVITE_CODE_REGEX = /^[A-Za-z0-9]{6}$/
const PASSWORD_REGEX = /^[A-Za-z0-9_@!#$%&*\-]{6,22}$/

export function getUsernameError(username) {
  if (!username) return '请输入用户名'
  if (!USERNAME_REGEX.test(username)) return '用户名仅支持中英文和数字，长度为5-12位'
  return ''
}

export function getEmailError(email) {
  if (!email) return '请输入邮箱'
  if (!EMAIL_360_REGEX.test(email)) return '邮箱格式不正确，且必须是 @360.cn 邮箱'
  return ''
}

export function getInviteCodeError(inviteCode) {
  if (!inviteCode) return '请输入邀请码'
  if (!INVITE_CODE_REGEX.test(inviteCode)) return '邀请码必须是6位字母或数字'
  return ''
}

export function getPasswordError(password) {
  if (!password) return '请输入密码'
  if (!PASSWORD_REGEX.test(password)) return '密码仅支持大小写英文、数字和 _-@!#$%&*，长度为6-22位'
  return ''
}

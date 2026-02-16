// 时间格式化工具：支持自定义格式
// 默认格式：YYYY-MM-dd HH:mm
export function formatDateTime(date, format = 'YYYY-MM-dd HH:mm') {
  const value = date instanceof Date ? date : new Date(date)
  const tokens = {
    YYYY: String(value.getFullYear()),
    MM: String(value.getMonth() + 1).padStart(2, '0'),
    dd: String(value.getDate()).padStart(2, '0'),
    HH: String(value.getHours()).padStart(2, '0'),
    mm: String(value.getMinutes()).padStart(2, '0'),
    ss: String(value.getSeconds()).padStart(2, '0')
  }

  return format.replace(/YYYY|MM|dd|HH|mm|ss/g, (token) => tokens[token])
}

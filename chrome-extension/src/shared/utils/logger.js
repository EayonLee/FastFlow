export const Logger = {
  info: (msg, ...args) => console.log(`[FastFlow] ${msg}`, ...args),
  warn: (msg, ...args) => console.warn(`[FastFlow] ${msg}`, ...args),
  error: (msg, ...args) => console.error(`[FastFlow] ${msg}`, ...args),
  step: (stepNum, msg) => console.log(`[FastFlow] ${stepNum}. ${msg}`)
}

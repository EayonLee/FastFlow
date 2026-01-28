export const Logger = {
  info: (msg, ...args) => console.log(`[FastFlow Copilot] ${msg}`, ...args),
  warn: (msg, ...args) => console.warn(`[FastFlow Copilot] ${msg}`, ...args),
  error: (msg, ...args) => console.error(`[FastFlow Copilot] ${msg}`, ...args),
  
  // 步骤日志
  step: (stepNum, msg) => console.log(`[FastFlow Copilot] ${stepNum}. ${msg}`)
};

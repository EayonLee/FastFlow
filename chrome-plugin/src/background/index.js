/**
 * FastFlow Chrome 插件后台服务脚本 (Service Worker)
 * 作用：处理插件的后台任务。
 * 注意：
 * 1. 使用 @crxjs/vite-plugin 后，热重载由插件自动管理，无需手动轮询。
 * 2. 此文件目前主要用于保持 Service Worker 活跃（如果需要）或处理其他后台逻辑。
 */

// 监听长连接，保持 Service Worker 活跃 (可选，视需求而定)
chrome.runtime.onConnect.addListener((port) => {
    if (port.name === 'keep-alive') {
        port.onDisconnect.addListener(() => {
            // console.log('Keep-alive 连接已断开');
        });
    }
});

console.log('[FastFlow-BG] Service Worker 已启动');

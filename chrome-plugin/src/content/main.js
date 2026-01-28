/**
 * FastFlow Chrome 插件主入口文件
 * 作用：初始化 Vue 应用，创建 Shadow DOM 容器，并将其挂载到宿主页面上。
 */

import { Logger } from '@/utils/logger.js'
import { Detector } from '@/utils/detector.js'
import { Bridge } from '@/services/bridge.js'
import { mountManager } from './mount.js'

let appInitialized = false;

/**
 * 主函数
 * 负责环境检测和启动流程
 */
function main() {
  if (appInitialized) return;
  
  // 检测是否在目标环境中（例如编排画布页面）
  if (Detector.check()) {
    const env = Detector.getEnvInfo();
    Logger.info(`在 [${env}] 中检测到编排画布，正在初始化...`);
    
    // 1. 注入通信桥接脚本
    Bridge.injectScript();
    
    // 2. 初始化 UI (使用新的 MountManager)
    mountManager.mount();
    
    appInitialized = true;
  }
}

// 开发环境 HMR (热重载) 适配
if (import.meta.hot) {
    import.meta.hot.accept();
    import.meta.hot.dispose(() => {
        console.log('[FastFlow] Cleaning up old UI for HMR...');
        mountManager.cleanup();
        appInitialized = false;
    });
}

// 保持 Service Worker 活跃 (仅在开发模式)
if (import.meta.env.MODE === 'development') {
    try {
        chrome.runtime.connect({ name: 'keep-alive' });
    } catch (e) {
        // 忽略连接错误
    }
}

// 确保在页面加载完成后执行 main
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(main, 100);
}

// 使用 MutationObserver 监听 DOM 变化，应对单页应用 (SPA) 的动态渲染
const observer = new MutationObserver((mutations) => {
  if (!appInitialized) {
    main();
  }
});

if (document.body) {
  observer.observe(document.body, { childList: true, subtree: true });
  setTimeout(main, 100); 
} else {
  window.addEventListener('DOMContentLoaded', () => {
    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(main, 100);
  });
}

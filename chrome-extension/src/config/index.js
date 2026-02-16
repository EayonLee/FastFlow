export const CONFIG = {
  // Nexus 服务地址
  API_BASE_URL: 'http://localhost:8080',
  // Nexus 服务地址
  NEXUS_BASE_URL: 'http://localhost:9090',
  // 用户密码加密密钥（与后端保持一致）
  PASSWORD_SECRET_KEY: 'd7b8a2c9e4f10536',
  // 全局登录校验轮询间隔（毫秒）
  AUTH_CHECK_INTERVAL_MS: 60 * 1000,
  // DOM 选择器：用于定位画布渲染容器，兼容 VueFlow/ReactFlow 不同实现
  ELEMENT_SELECTORS: [
    // VueFlow 根容器
    '.vue-flow-wrapper',
    // React Flow 根容器
    '.react-flow',
    // React Flow 渲染层
    '.react-flow__renderer',
    // React Flow 交互层（拖拽/缩放）
    '.react-flow__pane',
    // 兜底：任意包含 react-flow 的类名
    '[class*="react-flow"]',
    // 兜底：任意包含 vue-flow 的类名
    '[class*="vue-flow"]'
  ]
};

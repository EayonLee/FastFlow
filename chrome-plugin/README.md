```text
src/
├── background/         # Service Worker (后台服务)
│   └── index.js
├── content/            # Content Script (注入页面的聊天框应用)
│   ├── main.js         # 入口
│   ├── App.vue         # 根组件
│   └── views/          # 页面视图 (Chat.vue)
├── popup/              # Popup (浏览器右上角弹窗应用)
│   ├── main.js         # 入口
│   ├── App.vue         # 根组件 (原 Popup.vue)
│   └── popup.html      # 宿主 HTML
├── components/         # 共享组件 (FlowSelect 等)
├── styles/             # 共享样式
├── utils/              # 共享工具
└── services/           # 共享服务
```
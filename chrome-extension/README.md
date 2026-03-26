<div align="center">
  <img src="./src/public/logo.png" width="144" alt="FastFlow Chrome Extension Logo" />
  <h1>FastFlow Chrome Extension</h1>
  <p>基于 WXT + Vue 3 的 Chrome MV3 扩展，用于在页面内提供工作流感知聊天框、Popup 与页面注入桥。</p>
  <p>
    <a href="https://developer.chrome.com/docs/extensions/develop/migrate/what-is-mv3">
      <img alt="Chrome Extension MV3" src="https://img.shields.io/badge/Chrome%20Extension-MV3-2563eb?style=flat-square&logo=googlechrome&logoColor=white" />
    </a>
    <a href="https://wxt.dev">
      <img alt="WXT" src="https://img.shields.io/badge/WXT-0.20-111827?style=flat-square" />
    </a>
    <a href="https://vuejs.org">
      <img alt="Vue 3" src="https://img.shields.io/badge/Vue-3-059669?style=flat-square&logo=vuedotjs&logoColor=white" />
    </a>
    <img alt="Build Channels" src="https://img.shields.io/badge/Channels-development%20%7C%20production-0f766e?style=flat-square" />
    <img alt="Runtime Bridge" src="https://img.shields.io/badge/Runtime-background%20%2B%20content%20%2B%20inject-475569?style=flat-square" />
    <img alt="Chinese Docs" src="https://img.shields.io/badge/Docs-%E4%B8%AD%E6%96%87-0284c7?style=flat-square" />
  </p>
  <p>
    <a href="../README.md">返回仓库首页</a>
    ·
    <a href="#通过发行版安装推荐给非开发者">发行版安装</a>
    ·
    <a href="https://github.com/EayonLee/FastFlow">GitHub 仓库</a>
  </p>
</div>

## 简介

这是 FastFlow 的浏览器端子项目。它负责：

- 在页面内注入聊天框 UI，而不是跳转到独立控制台页面。
- 导出当前工作流图与工作流元信息，作为聊天请求上下文。
- 通过 background service worker 代理访问 API / Nexus，屏蔽页面侧的 CORS、Mixed Content 和宿主隔离问题。
- 通过 inject script 与页面上下文通信，完成工作流导入 / 导出。

如果你要了解整个仓库的三段式架构，请先看 [根 README](../README.md)。

## 通过发行版安装（推荐给非开发者）

如果你只是想安装插件，而不是参与扩展开发，推荐直接通过 GitHub Releases 安装。

发行版入口：

- 仓库右侧 `Releases`
- 直接访问：[FastFlow Releases](https://github.com/EayonLee/FastFlow/releases)

安装步骤：

1. 打开 [FastFlow Releases](https://github.com/EayonLee/FastFlow/releases)
2. 下载最新版本中的扩展发行包，文件名类似 `fastflow-<version>-chrome.zip`
3. 将 zip 解压到本地目录，例如 `~/Downloads/fastflow-1.1.1-chrome/`
4. 打开 Chrome，访问 `chrome://extensions`
5. 打开右上角“开发者模式”
6. 点击“加载已解压的扩展程序”
7. 选择刚才解压后的目录

重要说明：

- 不要直接选择 zip 文件；Chrome 这里需要的是“解压后的目录”
- 发行版本质上是 `production` 渠道的未打包扩展目录压缩包
- 如果你升级到新版本，下载新 release、重新解压后，在扩展页点击刷新，或移除旧目录后重新加载新目录

如果你需要的是本地联调或二次开发，再继续看下面的开发方式。

## 你会在这里做什么

常见开发任务基本都落在下面几类：

- 本地联调扩展 UI 和页面注入行为
- 切换 `development` / `production` 渠道构建
- 修改开发或生产环境的后端地址
- 固定扩展 ID，保证用户安装后的更新链路稳定
- 生成可直接加载的未打包扩展目录，或生成可分发 zip

## 快速开始（开发方式）

### 1. 环境要求

- Node.js
- npm
- Google Chrome

建议使用较新的 Node.js LTS 版本。

### 2. 安装依赖

```bash
cd chrome-extension
npm install
```

### 3. 可选：配置本地开发环境地址

本项目只允许通过 `.env.development.local` 覆盖开发环境地址，不允许用 `.env` 改写正式环境配置。

新建文件：

```bash
chrome-extension/.env.development.local
```

可选变量：

```bash
WXT_API_BASE_URL=http://127.0.0.1:8080
WXT_NEXUS_BASE_URL=http://127.0.0.1:9090
```

说明：

- 这个文件只影响 `development` 渠道。
- `production` 渠道地址固定由代码配置管理，不读本地 `.env` 覆盖。

### 4. 本地联调

推荐方式：

```bash
cd chrome-extension
npm run watch
```

这会以 `development` 渠道运行本地 watch，适合持续联调。

如果你只是想显式启动 WXT 默认开发流程，也可以使用：

```bash
npm run dev
# 或
npm run dev:chrome
```

### 5. 加载未打包扩展

先构建开发版：

```bash
cd chrome-extension
npm run build:dev
```

然后在 Chrome 中：

1. 打开 `chrome://extensions`
2. 打开右上角“开发者模式”
3. 点击“加载已解压的扩展程序”
4. 选择 `chrome-extension/dist/development`

## 常用命令

| 命令 | 作用 | 典型使用场景 |
| --- | --- | --- |
| `npm run dev` | 启动 WXT 默认开发服务器 | 快速验证 WXT 开发模式 |
| `npm run dev:chrome` | 显式以 Chrome 目标启动开发服务器 | 需要明确浏览器目标时 |
| `npm run watch` | 以 `development` 渠道持续 watch | 本地长期联调，推荐 |
| `npm run typecheck` | 运行 `vue-tsc` 类型检查 | 提交前自检 |
| `npm run build:dev` | 构建开发版未打包扩展 | 加载开发版、验证 development 渠道 |
| `npm run build:prod` | 构建正式版未打包扩展 | 验证 production 行为或给用户手动加载 |
| `npm run zip:prod` | 构建正式版并生成 zip | 分发包、商店上传准备 |
| `npm run clean` | 删除 `dist/` 并清理 WXT 缓存 | 构建异常、切渠道前做一次干净重建 |

## 渠道与产物

本项目固定分为两个发布渠道：

| 渠道 | 命令 | 产物目录 | 主要用途 |
| --- | --- | --- | --- |
| `development` | `npm run build:dev` / `npm run watch` | `dist/development/` | 本地联调，允许使用独立开发 ID |
| `production` | `npm run build:prod` / `npm run zip:prod` | `dist/production/` | 用户使用、正式验证、分发包 |

补充规则：

- `zip:prod` 会生成 `dist/fastflow-<version>-chrome.zip`
- `development` 和 `production` 使用不同的公钥，因此扩展 ID 不同
- `development` 的 `version_name` 会自动附加 `-dev`
- `production` 使用原始版本号

## 开发者最常改的配置

### 修改生产环境地址

位置：

- [`src/extension/config/channels.ts`](./src/extension/config/channels.ts)

关注字段：

- `production.apiBaseUrl`
- `production.nexusBaseUrl`

说明：

- `host_permissions` 会根据这两个地址自动生成
- 不需要手改 manifest

### 修改开发环境地址

位置：

- `.env.development.local`

可用变量：

- `WXT_API_BASE_URL`
- `WXT_NEXUS_BASE_URL`

### 修改版本号

位置：

- [`package.json`](./package.json)

字段：

```json
"version": "1.1.1"
```

规则：

- 这是唯一版本来源
- `build:prod` 会显示为 `1.1.1`
- `build:dev` 会显示为 `1.1.1-dev`

### 固定扩展 ID

位置：

- [`src/extension/config/keys.ts`](./src/extension/config/keys.ts)

说明：

- 这里保存的是开发版和正式版的扩展公钥
- Chrome 会基于 `manifest.key` 推导扩展 ID
- 正式版要保持稳定更新，`PROD_EXTENSION_PUBLIC_KEY` 不能随意改

### Manifest 生成入口

位置：

- [`wxt.config.ts`](./wxt.config.ts)
- [`src/extension/config/manifest.ts`](./src/extension/config/manifest.ts)

这里负责：

- 渠道切换
- `manifest.key`
- `host_permissions`
- `version_name`
- `web_accessible_resources`

## 目录结构

```text
src/
├── apps/
│   ├── chatbox/        # 注入页面的聊天框应用
│   └── popup/          # Popup Vue 应用
├── entrypoints/
│   ├── background.ts   # WXT background 入口
│   ├── content.ts      # WXT content script 入口
│   ├── inject.ts       # WXT unlisted script 入口
│   └── popup.html      # WXT popup 页面
├── extension/
│   ├── background/     # service worker 与后台请求处理
│   ├── config/         # 渠道配置、manifest 工厂、运行时配置
│   ├── content/        # content script 生命周期
│   ├── inject/         # 页面注入桥
│   ├── protocol/       # 扩展内部协议常量
│   └── runtime/        # 扩展通信桥与后台客户端
├── public/
│   └── logo.png        # 扩展图标
└── shared/
    ├── components/     # 跨 app 共享组件
    ├── composables/    # 跨 app 共享组合式逻辑
    ├── services/       # 面向业务的共享服务
    ├── styles/         # 共享样式
    └── utils/          # 通用工具
```

目录边界原则：

- `src/apps` 只放具体 Vue 应用
- `src/entrypoints` 只放 WXT 入口
- `src/extension` 只放扩展运行时逻辑
- `src/shared` 放跨 app 复用代码

## 运行方式与数据流

这部分是扩展开发里最容易搞混的地方。

### UI 层

- `popup`：扩展按钮弹出的独立页面
- `chatbox`：注入到宿主页面中的聊天框

### 运行时层

- `content script`：运行在页面隔离上下文，负责挂载 UI、桥接页面与扩展
- `inject script`：运行在页面真实上下文，负责调用页面内工作流导入导出能力
- `background service worker`：扩展唯一允许直接访问后端的位置

### 请求链路

```text
Chatbox / Popup
  -> runtime backend client
  -> background service worker
  -> API / Nexus
  -> SSE / HTTP 结果回传前端
```

设计约束：

- 页面侧不能直接请求后端
- 所有 API / Nexus 请求统一走 background
- `inject.js` 必须通过 `web_accessible_resources` 暴露给页面

## 加载、验证与分发

### 开发版加载

```bash
npm run build:dev
```

加载目录：

- `dist/development/`

### 正式版加载

```bash
npm run build:prod
```

加载目录：

- `dist/production/`

### 正式版分发

```bash
npm run zip:prod
```

分发文件：

- `dist/fastflow-<version>-chrome.zip`

说明：

- 本地验证时，优先直接加载 `dist/production/`
- `zip:prod` 更适合给别人分发或作为商店上传包
- 给用户分发时，应告知“先解压，再在 `chrome://extensions` 中加载已解压目录”

## 常见问题

### 1. 改了版本号，但页面里没变

先确认两件事：

- 你改的是 [`package.json`](./package.json) 里的 `version`
- 你重新执行了 `build:dev` 或 `build:prod`

然后在 Chrome 扩展页重新加载扩展。

### 2. 改了默认宽度，但聊天框没变化

聊天框尺寸有本地缓存。默认宽度只对“没有缓存尺寸”的场景生效。  
相关逻辑在 `chatbox` 视图里，缓存 key 是 `chat_box_size`。

### 3. 扩展加载报 manifest 或资源异常

优先执行：

```bash
npm run clean
npm run build:prod
```

然后重新加载 `dist/production/`，不要复用旧解压目录。

### 4. 我只想知道现在该改哪里

- 改生产地址：[`src/extension/config/channels.ts`](./src/extension/config/channels.ts)
- 改版本号：[`package.json`](./package.json)
- 改扩展公钥 / 固定 ID：[`src/extension/config/keys.ts`](./src/extension/config/keys.ts)
- 改 manifest 规则：[`src/extension/config/manifest.ts`](./src/extension/config/manifest.ts)

## 相关文档

- [仓库首页](../README.md)
- [WXT 文档](https://wxt.dev)
- [Chrome Extensions 文档](https://developer.chrome.com/docs/extensions)
- [Manifest V3 概览](https://developer.chrome.com/docs/extensions/develop/migrate/what-is-mv3)

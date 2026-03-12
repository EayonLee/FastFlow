<div align="center">
  <img src="../chrome-extension/src/public/logo.png" width="128" alt="FastFlow Nexus Logo" />
  <h1>FastFlow Nexus</h1>
  <p>基于 FastAPI 的智能体执行层，负责模型调用、工具调度、SSE 流式事件输出与工作流上下文处理。</p>
  <p>
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0f766e?style=flat-square&logo=fastapi&logoColor=white" />
    <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2563eb?style=flat-square&logo=python&logoColor=white" />
    <img alt="LangChain" src="https://img.shields.io/badge/LangChain-1.0-166534?style=flat-square" />
    <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-1.0-0f172a?style=flat-square" />
    <img alt="LiteLLM" src="https://img.shields.io/badge/LiteLLM-enabled-7c3aed?style=flat-square" />
    <img alt="SSE Stream" src="https://img.shields.io/badge/Transport-SSE-f59e0b?style=flat-square" />
    <img alt="Port 9090" src="https://img.shields.io/badge/Port-9090-0284c7?style=flat-square" />
  </p>
  <p>
    <a href="../README.md">返回仓库首页</a>
    ·
    <a href="../chrome-extension/README.md">扩展文档</a>
    ·
    <a href="../api/README.md">API 文档</a>
  </p>
</div>

## 简介

`nexus/` 是 FastFlow 的智能体执行层。它对外暴露统一的流式接口，内部负责：

- 接收聊天请求与工作流上下文
- 调用模型并执行工具链
- 输出标准化 SSE 事件
- 提供 Slash 面板目录
- 维护短期会话历史、工具循环保护与回答复核策略

默认端口：`9090`

## 快速开始

### 1. 环境要求

- Python 3.10+
- `pip`

### 2. 安装依赖

```bash
cd nexus
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 启动服务

```bash
cd nexus
python -m nexus.main
```

默认监听地址与端口：

- Host：`0.0.0.0`
- Port：`9090`

## 常用命令

```bash
cd nexus

python -m nexus.main              # 启动服务
python -c "from nexus.main import app; print(app.title)"   # 最小导入检查
```

如果你在虚拟环境中运行，别忘了先：

```bash
source .venv/bin/activate
```

## 配置方式

配置入口：

- [`config/config.py`](./config/config.py)
- [`main.py`](./main.py)
- [`.env`](./.env)

### 配置加载规则

- `config.py` 使用 `pydantic-settings`
- 默认会读取 `nexus/.env`
- 未提供时使用代码中的默认值

### 常用环境变量

| 变量 | 说明 |
| --- | --- |
| `APP_NAME` | 服务名，默认 `FastFlow-Nexus` |
| `APP_HOST` | 监听地址，默认 `0.0.0.0` |
| `APP_PORT` | 监听端口，默认 `9090` |
| `APP_VERSION` | 服务版本 |
| `FASTFLOW_API_URL` | API 模块地址，默认 `http://localhost:8080` |
| `LOG_LEVEL` | 日志级别 |
| `LOG_FORMAT` | 日志格式 |
| `SESSION_HISTORY_MAX_MESSAGES` | 单个 session 的消息保留上限 |
| `SESSION_HISTORY_EXPIRE_SECONDS` | 会话过期时间 |
| `TOOL_MAX_CALLS_PER_QUESTION` | 单个问题允许的工具调用上限 |
| `CHAT_ANSWER_SUFFICIENCY_MAX_REVIEW_ROUNDS` | 回答复核最大回环次数 |

说明：

- 这个模块的运行行为比较依赖 `.env` 和模型配置，调试时优先检查这里。
- 如果要联通 API，请先确认 `FASTFLOW_API_URL` 指向正确的 `8080` 服务。

## 路由与对外能力

基础路由前缀：

- `/fastflow/nexus/v1`

主要对外接口：

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/fastflow/nexus/v1/health` | `GET` | 健康检查 |
| `/fastflow/nexus/v1/agent/chat/completions` | `POST` | 统一智能体流式接口 |
| `/fastflow/nexus/v1/slash/catalog` | `GET` | Slash 面板目录 |

路由注册入口：

- [`api/routes/router.py`](./api/routes/router.py)

健康检查入口：

- [`api/metrics.py`](./api/metrics.py)

Agent 接口入口：

- [`api/agent.py`](./api/agent.py)

## SSE 事件模型

`/agent/chat/completions` 会返回 `text/event-stream`，扩展侧会消费这些标准事件。

当前核心事件包括：

- `run.started`
- `phase.started`
- `phase.completed`
- `answer.delta`
- `answer.done`
- `thinking.delta`
- `thinking.summary`
- `run.completed`
- `error`

事件定义位置：

- [`core/event/execution_events.py`](./core/event/execution_events.py)

服务层会在事件中附带：

- `session_id`
- `seq`
- `ts`

相关逻辑位置：

- [`services/agent_service.py`](./services/agent_service.py)

## 目录结构

```text
nexus/
├── agents/      # 智能体实现
├── api/         # FastAPI 路由层
├── common/      # 通用异常与依赖
├── config/      # 配置与日志
├── core/        # event / llm / prompts / tools / skills / cache
├── Dockerfile   # Nexus 运行镜像
├── base.Dockerfile  # Nexus 基础镜像
├── services/    # 服务层
├── skills/      # 本地 skills
├── main.py      # 应用入口
└── requirements.txt
```

对开发者来说，最常看的位置一般是：

- `api/`：接口边界
- `services/`：流式响应和业务编排
- `agents/`：智能体主逻辑
- `core/event/`：SSE 事件模型
- `core/tools/`：工具调用
- `core/skills/` 与 `skills/`：技能系统

## 运行链路

```text
Chrome Extension
  -> POST /fastflow/nexus/v1/agent/chat/completions
  -> ChatAgent / tools / review loop
  -> SSE events
  -> [DONE]
```

几个关键点：

- 这是流式服务，不是一次性 JSON 响应接口
- `chat` 模式要求 `model_config_id`
- `builder` / `debugger` 当前保留入口，但返回固定占位响应
- 服务层在正常结束时会显式输出 `data: [DONE]`

## 与其他模块的关系

```text
Chrome Extension
  -> Nexus
  -> API

Nexus
  -> LLM / LiteLLM
  -> 本地 tools / skills
  -> FastFlow API
```

说明：

- 扩展会把当前工作流图和工作流元信息一并发给 Nexus
- Nexus 需要依赖 `FASTFLOW_API_URL` 回调或读取 API 侧能力
- 这个模块是“智能体行为”和“流式协议”的核心实现层

## Docker

Docker 入口：

- [`Dockerfile`](./Dockerfile)
- [`base.Dockerfile`](./base.Dockerfile)

镜像行为：

- 暴露端口 `9090`
- 健康检查路径为 `/fastflow/nexus/v1/health`
- 运行入口固定为：

```bash
python -m nexus.main
```

推荐从 `nexus/` 目录作为构建上下文执行：

```bash
cd nexus

docker build -f base.Dockerfile -t fastflow-nexus-base:latest .
docker build -f Dockerfile -t fastflow-nexus:latest .
```

如果你在 IDEA 中构建，也要保持一致：

- `Dockerfile` 选择 `nexus/Dockerfile` 或 `nexus/base.Dockerfile`
- `Build context` 固定为 `nexus/`

不要把 `Build context` 指到 Dockerfile 所在目录，否则 `COPY requirements.txt ...` 会找不到文件。

## 当前状态

- `chat` 是当前主稳定入口
- `builder` 与 `debugger` 目前保留但未开放完整能力
- 扩展侧已经依赖这里输出的 SSE 事件模型，因此改事件类型要非常谨慎
- 如果扩展界面卡在 loading，通常优先检查这里是否按预期输出了终态事件和 `[DONE]`

## 排查建议

### 1. 扩展发起请求后一直 loading

优先确认：

- Nexus 是否收到了请求
- 是否输出了 `answer.done` / `run.completed`
- 是否最终输出了 `data: [DONE]`

### 2. 扩展收不到回答

优先确认：

- `APP_PORT` 是否真的是 `9090`
- 扩展的 `nexusBaseUrl` 是否指向正确地址
- `Authorization` 是否有效

### 3. Slash 面板没有内容

优先确认：

- `/fastflow/nexus/v1/slash/catalog` 是否可访问
- 本地 `skills/` 目录里是否有可见技能

## 相关文档

- [仓库首页](../README.md)
- [Chrome Extension 文档](../chrome-extension/README.md)
- [API 文档](../api/README.md)

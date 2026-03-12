<div align="center">
  <img src="../chrome-extension/src/public/logo.png" width="128" alt="FastFlow API Logo" />
  <h1>FastFlow API</h1>
  <p>基于 Spring Boot 3 的业务 API，负责认证、用户、模型配置、工作流与 Nexus 编排入口。</p>
  <p>
    <img alt="Spring Boot 3" src="https://img.shields.io/badge/Spring%20Boot-3.x-16a34a?style=flat-square&logo=springboot&logoColor=white" />
    <img alt="Java 17" src="https://img.shields.io/badge/Java-17-ea580c?style=flat-square&logo=openjdk&logoColor=white" />
    <img alt="Maven" src="https://img.shields.io/badge/Build-Maven-c2410c?style=flat-square&logo=apachemaven&logoColor=white" />
    <img alt="PostgreSQL" src="https://img.shields.io/badge/Database-PostgreSQL-2563eb?style=flat-square&logo=postgresql&logoColor=white" />
    <img alt="Port 8080" src="https://img.shields.io/badge/Port-8080-0f766e?style=flat-square" />
    <img alt="Profiles dev test prod" src="https://img.shields.io/badge/Profiles-dev%20%7C%20test%20%7C%20prod-475569?style=flat-square" />
  </p>
  <p>
    <a href="../README.md">返回仓库首页</a>
    ·
    <a href="../chrome-extension/README.md">扩展文档</a>
    ·
    <a href="../nexus/README.md">Nexus 文档</a>
  </p>
</div>

## 简介

`api/` 是 FastFlow 的业务 API 模块。它不是一个“纯透传层”，而是整个系统中负责业务边界和基础能力的后端服务。

当前职责主要包括：

- 用户注册、登录和登录态校验
- 模型配置管理
- 工作流与画布相关接口
- 邀请码相关接口
- Slash / Clash 目录接口
- 向 Nexus 暴露统一的业务服务入口与基础配置

默认端口：`8080`

## 快速开始

### 1. 环境要求

- Java 17
- Maven
- PostgreSQL

### 2. 启动服务

```bash
cd api
mvn spring-boot:run
```

默认 profile 是 `dev`，默认端口是 `8080`。

### 3. 常用命令

```bash
cd api

mvn spring-boot:run   # 本地启动
mvn test              # 运行测试
mvn clean package     # 打包产物
```

### 4. 运行 jar

如果你已经打包完成，也可以直接运行 jar：

```bash
cd api
mvn clean package
java -jar target/api-1.0-SNAPSHOT.jar
```

## 配置方式

配置入口：

- [`src/main/resources/application.yml`](./src/main/resources/application.yml)
- [`src/main/resources/application-dev.yml`](./src/main/resources/application-dev.yml)
- [`src/main/resources/application-test.yml`](./src/main/resources/application-test.yml)
- [`src/main/resources/application-prod.yml`](./src/main/resources/application-prod.yml)

### 配置优先级

- 公共配置放在 `application.yml`
- 环境差异配置放在 `application-<profile>.yml`
- 当前默认 profile 为 `dev`
- 可通过环境变量切换 profile：

```bash
SPRING_PROFILES_ACTIVE=prod mvn spring-boot:run
```

### 常用环境变量

| 变量 | 说明 |
| --- | --- |
| `SERVER_PORT` | API 服务端口，默认 `8080` |
| `SPRING_PROFILES_ACTIVE` | 启动 profile，默认 `dev` |
| `NEXUS_BASE_URL` | Nexus 服务地址，默认 `http://localhost:9090` |
| `DEV_DB_URL` / `PROD_DB_URL` / `TEST_DB_URL` | PostgreSQL 连接地址 |
| `DEV_DB_USERNAME` / `PROD_DB_USERNAME` / `TEST_DB_USERNAME` | 数据库用户名 |
| `DEV_DB_PASSWORD` / `PROD_DB_PASSWORD` / `TEST_DB_PASSWORD` | 数据库密码 |
| `DEV_AUTH_JWT_SECRET` / `PROD_AUTH_JWT_SECRET` / `TEST_AUTH_JWT_SECRET` | JWT Secret |
| `DEV_AUTH_PASSWORD_SECRET_KEY` / `PROD_AUTH_PASSWORD_SECRET_KEY` / `TEST_AUTH_PASSWORD_SECRET_KEY` | 密码相关密钥 |

说明：

- `application-dev.yml` 和 `application-test.yml` 里有默认值，但生产环境不要依赖默认值。
- `prod` profile 下数据库和鉴权相关配置都应该显式通过环境变量传入。

## 模块结构

```text
src/main/java/com/fastflow/
├── controller/   # HTTP 接口层
├── service/      # 业务逻辑层
├── mapper/       # MyBatis Plus 数据访问层
├── entity/       # DTO / VO / Entity
├── common/       # 通用结果、异常、拦截器、注解
└── config/       # Spring 配置
```

你通常会在这些位置修改代码：

- 新增或修改接口：`controller/`
- 新增业务逻辑：`service/`
- 改数据访问：`mapper/`
- 改统一结果、异常或鉴权：`common/`

## 主要接口分组

当前控制器前缀主要包括：

| 分组 | 路径前缀 |
| --- | --- |
| 认证 | `/fastflow/api/v1/auth` |
| 用户 | `/fastflow/api/v1/user` |
| 模型配置 | `/fastflow/api/v1/model_config` |
| 工作流 | `/fastflow/api/v1/workflow` |
| 画布 | `/fastflow/api/v1/workflow/canvas` |
| 工作流节点 | `/fastflow/api/v1/workflow/node` |
| 邀请码 | `/fastflow/api/v1/inviteCode` |
| Slash / Clash | `/fastflow/api/v1/clash` |

如果你只看一个入口类，优先看：

- [`src/main/java/com/fastflow/FastFlowApplication.java`](./src/main/java/com/fastflow/FastFlowApplication.java)

如果你只看一个典型控制器，优先看：

- [`src/main/java/com/fastflow/controller/user/AuthController.java`](./src/main/java/com/fastflow/controller/user/AuthController.java)

## 与其他模块的关系

```text
Chrome Extension
  -> FastFlow API
  -> Nexus

FastFlow API
  -> PostgreSQL
  -> Nexus (via NEXUS_BASE_URL)
```

关键点：

- API 默认认为 Nexus 运行在 `http://localhost:9090`
- 扩展的业务请求会先打到 API，部分能力再由 API 关联到 Nexus
- 这个模块是浏览器端认证和业务配置的核心边界

## Docker

当前 Docker 运行方式依赖“宿主机已经先打包 jar”：

1. 先执行：

```bash
cd api
mvn clean package
```

2. 然后再基于：

- [`Dockerfile`](./Dockerfile)

说明：

- 容器默认暴露 `8080`
- 运行产物固定为 `target/api-1.0-SNAPSHOT.jar`
- 镜像支持通过 `/app/config` 额外挂载配置

## 当前状态

- 这是一个典型的 Spring Boot 单体业务 API 模块
- 默认 profile 是 `dev`
- 数据层依赖 PostgreSQL
- 与 `chrome-extension`、`nexus` 联动时，`NEXUS_BASE_URL` 是最重要的跨模块配置之一

## 相关文档

- [仓库首页](../README.md)
- [Chrome Extension 文档](../chrome-extension/README.md)
- [Nexus 文档](../nexus/README.md)

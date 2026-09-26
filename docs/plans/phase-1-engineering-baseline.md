# Phase 1 Implementation Plan

## Goal

建立可构建、可测试、可部署的 Monorepo 工程骨架，并把 Product Spec 中跨 Backend、Android、Web Admin 的 V1 状态、错误、版本和能力语义固化为共享契约。

本阶段只提供工程基础设施、接口契约、stub/fake/mock 和集成验证，不实现认证、业务数据库、文件存储或正式任务执行逻辑。

## Progress

- Task 1 — COMPLETE
- Task 2 — COMPLETE
- Task 3 — COMPLETE
- Task 4 — COMPLETE
- Task 5 — COMPLETE
- Task 6 — COMPLETE
- Task 7 — COMPLETE
- Task 8 — COMPLETE
- Task 9 — COMPLETE
- Task 10 — COMPLETE
- Phase 1 Exit Checklist — PASS
- Last verified: 2026-09-26
- Next: Return to $planning to create the Phase 2 Implementation Plan

## Confirmed Inputs

已检查：

- [Project Implementation Roadmap](../roadmap/implementation-roadmap.md)
- [Product Spec](../superpowers/specs/2026-09-23-android-virtual-try-on-design.md)
- [Product Flow](../product-flow.md)
- [Android UI Spec](../superpowers/specs/2026-09-23-android-v1-ui-design.md)
- [Web Admin UI Spec](../superpowers/specs/2026-09-24-web-admin-ui-design.md)
- [Web Admin Visual Direction](../superpowers/specs/2026-09-24-web-admin-visual-direction.md)
- [DESIGN.md](../../DESIGN.md)
- Web Admin 静态原型
- 当前 Repository 全部非 Git 文件

当前状态：

- 目录尚不是 Git repository。
- 不存在 Backend、Android、Web Admin、CI、部署、依赖或测试工程。
- 现有文件均为已确认规格、设计和静态原型；没有生产代码需要迁移或兼容。
- Product Spec 是产品行为权威来源；Product Flow 用于核对状态流。
- Android/Web UI Spec 和 `DESIGN.md` 只约束后续 UI 实现，本阶段不重新设计。

## Technical Decisions

### 1. Monorepo

采用单 Git repository：

- `backend/`
- `android/`
- `web-admin/`
- `contracts/`
- `infra/`
- `docs/adr/`
- `.github/workflows/`

原因：项目由同一个人维护，共享一个 API 生命周期；契约、客户端生成和跨端 CI 在同一提交中更容易保持一致。

### 2. Backend

采用：

- Python 3.14
- FastAPI 0.141 系列
- Pydantic 2 / pydantic-settings
- Uvicorn
- 模块化单体
- `uv` 管理依赖和 `uv.lock`
- Ruff 负责格式和 lint
- Pyright 负责静态类型检查
- Pytest 负责测试

Python 3.14 已是稳定版本；具体 patch 和 Python 包解析结果写入锁文件，不使用浮动生产安装。[Python 3.14](https://www.python.org/downloads/release/python-3140/)；`uv.lock` 提供可复现的精确依赖解析，并应提交仓库。[uv locking](https://docs.astral.sh/uv/concepts/projects/sync/)

后端按业务能力分包，不采用全局 `models/services/controllers` 大目录：

- `auth`
- `assets`
- `jobs`
- `providers`
- `workflows`
- `admin`
- `cleanup`

`Outfits` 属于 Phase 9，本阶段不创建业务实现；只确保公共契约没有把 V1 结构写死到无法扩展。

### 3. Database and migrations

采用：

- SQLite
- SQLAlchemy 2 async API
- `sqlite+aiosqlite`
- Repository + Unit of Work 边界
- Alembic migrations

业务服务不得直接散布 SQL 或依赖 SQLite-specific 行为。SQLAlchemy 已正式支持 `aiosqlite` async dialect。[SQLAlchemy SQLite async support](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)

Phase 1 只建立连接、事务、migration 和 smoke test，不创建 Phase 2–9 的正式业务 schema。

基础 SQLite 设置：

- foreign keys enabled
- WAL mode
- bounded busy timeout
- migrations 串行执行
- 数据库文件和私有文件目录位于持久卷

### 4. API contract ownership

采用 spec-first OpenAPI：

- OpenAPI 3.0.3 是唯一跨端 HTTP 契约源。
- 源文件位于 `contracts/openapi/`，按 domain 拆分。
- CI 生成单一 bundled artifact。
- Backend Pydantic contract models、Android client、Web types/client 均从同一契约生成。
- 生成代码可以提交，但必须标记为 generated，禁止手改；CI 验证无 drift。
- Backend 通过 request/response contract tests 验证实现符合规范。
- Mock server 直接从 bundled OpenAPI 启动。

业务规则仍归 Product Spec；OpenAPI 只表达已确认边界，不成为新的产品需求来源。

### 5. Web Admin

采用：

- React 19
- TypeScript
- Vite 8
- React Router
- TanStack Query
- React Hook Form + Zod
- 原生 CSS variables + CSS Modules
- Vitest + Testing Library
- Playwright smoke tests

不引入整套视觉组件库，以免 Phase 7 被默认组件皮肤约束。

工具链采用 Node.js 24 LTS、pnpm 10、`pnpm-lock.yaml`；Node 24 当前为 LTS。[Node release schedule](https://nodejs.org/en/about/previous-releases) Vite 依赖锁定到 8.x 当前受支持 minor，不使用动态版本。[Vite releases](https://vite.dev/releases)

### 6. Android baseline

采用：

- Kotlin
- Jetpack Compose + Material 3
- Coroutines / Flow
- Navigation Compose
- Hilt
- Retrofit + OkHttp + Kotlin serialization
- OpenAPI-generated contract module
- JUnit、Compose UI test、Android lint

工程仅建立：

- `:app`
- `:core:api-contract`

业务 feature 先使用 `app` 内 feature packages；不在空仓库阶段提前拆分大量 Gradle modules。

版本基线：

- JDK 17
- AGP 9.2.1
- Gradle 9.4.1
- Kotlin 2.2.10
- compile/target SDK 37
- min SDK 26
- Compose BOM `2026.09.00`

选择已发布一段时间的 AGP 9.2，而不是刚发布的 9.4；Compose 依赖通过官方 BOM 统一管理。[AGP 9.2 compatibility](https://developer.android.com/build/releases/agp-9-2-0-release-notes) [Compose BOM](https://developer.android.com/develop/ui/compose/bom)

### 7. Configuration and secrets

Backend 配置按 Product Spec 分层：

- 部署级：环境变量或本地 `.env`
- 运行时业务配置：后续存入数据库，由 Admin 管理
- Workflow 文件：后续进入受控 FileStorage，数据库只保存版本和引用

建议统一前缀：`CLOTHES_MODEL_`。

Phase 1 环境模板至少包括：

- environment/profile
- bind host/port
- database URL
- storage root
- log level
- CORS allowlist
- scheduler enabled
- instance lock path
- encryption master-key file path
- admin session cookie security flags

Secret 边界：

- `.env.example` 只含占位符。
- 开发环境允许本地 `.env`，必须被 Git 忽略。
- V1 部署通过只读 secret file 或宿主环境注入；优先使用 `*_FILE`。
- Secret 不允许出现在命令行参数、镜像层、Web bundle、Android resources、日志或 OpenAPI examples。
- Provider Secret 的数据库加密属于 Phase 2，不在 Phase 1 实现。

### 8. Testing baseline

- Contracts：lint、bundle、breaking-change check、mock startup、codegen freshness。
- Backend：health/config smoke、OpenAPI conformance、migration smoke、single-instance guard。
- Web：unit/component smoke、typecheck、lint、production build、mock API browser smoke。
- Android：unit smoke、lint、`assembleDebug`、generated client compilation；Compose instrumented test设施建立但不要求 Phase 1 CI 启动 emulator。
- Deployment：container build、migration invocation、health/readiness smoke。

### 9. CI baseline

采用 GitHub Actions，任务并行但具有以下依赖：

```text
contract
 ├── backend
 ├── web-admin
 └── android
        ↓
 deployment-smoke
```

所有依赖安装必须使用 lockfile/frozen 模式。

### 10. Local development

开发模式提供：

- OpenAPI contract mock server
- Backend dev server
- Vite dev server
- Android debug base URL 配置
- Docker Compose 集成环境

Android emulator 通过 `10.0.2.2` 访问宿主 mock/backend；真实设备地址通过 debug-only 配置注入，不写死在生产资源。

### 11. V1 deployment and single-instance constraint

V1 部署为固定 Linux 服务器上的 Docker Compose：

- Caddy：HTTPS 和反向代理
- 单个 application container：Backend + Web Admin 静态构建
- SQLite 持久卷
- 私有文件持久卷
- secret mount

强制约束：

- Backend replica 必须为 1。
- Uvicorn worker 必须为 1。
- Scheduler 与 HTTP 服务处于同一进程。
- 启动时在持久数据目录获取 instance lock；第二实例获取失败则 fail fast。
- 不引入 Redis、Celery、独立 Worker、Kubernetes 或多 ComfyUI 节点。
- 如未来需要多实例，必须先更换任务领取协调机制和数据库方案，不能只提高 replica 数。

## ADRs

Phase 1 创建以下 ADR：

1. `0001-monorepo-and-toolchains.md`
   - Monorepo 边界
   - 三端工具链
   - lockfile 和 generated-code 政策

2. `0002-backend-modular-monolith.md`
   - Python/FastAPI
   - feature-first 模块边界
   - HTTP/application/domain/infrastructure 依赖方向

3. `0003-sqlite-sqlalchemy-alembic.md`
   - SQLite
   - async SQLAlchemy
   - repository/UoW
   - migration ownership和未来迁移边界

4. `0004-openapi-contract-ownership.md`
   - spec-first
   - OpenAPI source、bundle、mock、client generation
   - breaking-change policy

5. `0005-v1-single-instance-runtime.md`
   - 一个应用进程、一个调度器
   - replica/worker 限制
   - instance lock
   - SQLite 持久卷约束

普通 UI、lint、测试库依赖不单独创建 ADR。

## Target Repository Structure

```text
clothes_model/
├── .github/
│   └── workflows/
│       └── ci.yml
├── android/
│   ├── app/
│   ├── core/
│   │   └── api-contract/
│   ├── gradle/
│   │   └── libs.versions.toml
│   ├── build.gradle.kts
│   ├── settings.gradle.kts
│   ├── gradle.properties
│   └── gradlew / gradlew.bat
├── backend/
│   ├── src/clothes_model/
│   │   ├── api/
│   │   ├── core/
│   │   ├── infrastructure/
│   │   │   ├── database/
│   │   │   ├── scheduler/
│   │   │   └── storage/
│   │   └── modules/
│   │       ├── auth/
│   │       ├── assets/
│   │       ├── jobs/
│   │       ├── providers/
│   │       ├── workflows/
│   │       ├── admin/
│   │       └── cleanup/
│   ├── migrations/
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
├── contracts/
│   ├── openapi/
│   │   ├── openapi.yaml
│   │   ├── paths/
│   │   ├── components/
│   │   │   ├── common/
│   │   │   ├── auth/
│   │   │   ├── assets/
│   │   │   ├── jobs/
│   │   │   ├── providers/
│   │   │   ├── workflows/
│   │   │   └── admin/
│   │   └── examples/
│   ├── generated/
│   │   └── openapi.yaml
│   └── tooling/
├── docs/
│   ├── adr/
│   ├── roadmap/
│   └── superpowers/
├── infra/
│   ├── compose.yaml
│   ├── Caddyfile
│   └── docker/
├── prototypes/
├── web-admin/
│   ├── src/
│   │   ├── api/
│   │   ├── app/
│   │   └── features/
│   ├── tests/
│   ├── package.json
│   └── vite.config.ts
├── .editorconfig
├── .env.example
├── .gitignore
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── README.md
└── DESIGN.md
```

## Contract Strategy

### Resource boundaries

| Resource | Boundary |
|---|---|
| Authentication | App Bearer token；Admin Token 只用于建立 HttpOnly Cookie session；Admin 写操作预留 CSRF 防护 |
| Uploads | 独立 `UploadSession`，表达创建、传输进度、完成、失败、取消与恢复；完成后产生 Asset |
| Assets | `Asset` 为文件元数据，`PersonAsset` / `GarmentAsset` 为领域视图；文件内容通过受认证 content endpoint |
| Jobs | `TryOnJob` 是聚合根，锁定输入、生成参数和版本引用 |
| JobItems | 候选执行单元，可独立取消和重试；旧 attempt 不覆盖 |
| Outputs | 从属于 JobItem，引用服务器持久化 Asset；删除图片不删除谱系 |
| Providers | 客户端可读取可选 Provider、可用性和 capability snapshot |
| Provider Configurations | Admin-only，不与客户端可选 Provider 视图混用；Secret 永不回显 |
| Workflows | Admin-only immutable versions；`draft/validated/active/retired` |
| Admin Configuration | 显式资源：默认 Provider、Comfy node、retention policy；不设计无类型 key-value 配置 API |
| Storage | Admin-only capacity、blocking state、scan/cleanup command boundaries |
| Diagnostics | Admin-only、脱敏、含 snapshot time、job lineage、locked refs 和 safe external execution metadata |

### URL and wire conventions

- API base：`/api/v1`
- 普通用户资源：`/api/v1/...`
- 管理资源：`/api/v1/admin/...`
- Health：`/health/live`、`/health/ready`
- JSON 字段：`snake_case`
- ID：UUIDv7 字符串
- 时间：UTC RFC 3339
- 单资源直接返回 resource
- 列表统一返回：

```json
{
  "items": [],
  "next_cursor": null,
  "has_more": false
}
```

分页使用 opaque cursor 和 `limit`；默认 50，最大 100。稳定排序至少包含 `created_at` 和 `id`。

### Shared states

`JobState`：

```text
queued
waiting_provider
preparing
running
needs_attention
succeeded
partially_succeeded
failed
cancelled
unknown
```

`JobItemState`：

```text
queued
waiting_provider
preparing
running
needs_attention
succeeded
failed
cancelled
unknown
```

`partially_succeeded` 只属于主任务聚合。

`needs_attention` 重试的契约语义：

- 原 JobItem 保留原执行和不确定状态记录。
- 创建一个带 `retry_of_job_item_id` 的新 JobItem。
- 新 JobItem 从 `queued` 开始。
- 主任务状态根据全部有效候选重新汇总。
- Product Flow 中的 `needs_attention → running` 解释为主任务在新子任务推进后的聚合表现，不是覆盖原外部执行记录。

阻塞原因独立于状态，至少预留：

- `provider_offline`
- `storage_capacity`
- `retry_backoff`
- `locked_configuration_unavailable`
- `external_state_unknown`
- `configuration_invalid`

### Error model

使用 `application/problem+json`：

```json
{
  "type": "https://.../problems/idempotency-key-reused",
  "title": "请求无法处理",
  "status": 409,
  "code": "idempotency_key_reused",
  "detail": "该幂等键已用于不同请求。",
  "trace_id": "...",
  "retryable": false,
  "field_errors": [],
  "context": {}
}
```

要求：

- `code` 稳定、机器可判定。
- `detail` 是可展示中文信息，但客户端不得通过字符串判断逻辑。
- `context` 只允许安全字段。
- 外部原始错误、Token、Secret、完整正文和图片信息不得进入公共响应。
- 未知错误码由客户端映射到安全通用错误状态。

### Idempotency

以下命令要求 `Idempotency-Key`：

- 创建上传会话
- 完成上传
- 创建任务
- 创建重试
- 创建遮罩修正任务
- 其他可能生成费用或新谱系的命令

服务端按 actor scope + operation + key 保存请求摘要和结果：

- 相同 key、相同 payload：返回同一资源/结果。
- 相同 key、不同 payload：`409 idempotency_key_reused`。
- 幂等记录至少与其创建资源的审计生命周期一致。
- Cancel 等天然幂等命令仍接受 key，重复请求返回当前稳定状态。

### Version references

历史任务不得引用 `current`、`default` 或 `active` 别名。

统一显式引用：

```text
ProviderConfigRef:
  provider_id
  config_version_id
  revision

WorkflowVersionRef:
  workflow_id
  workflow_version_id
  version
```

任务响应同时返回 locked reference 和面向 UI 的只读 snapshot label。配置变更只能影响新任务。

### Capability representation

使用结构化 `ProviderCapabilities`，不使用任意字符串数组：

- garment categories
- manual mask
- multiple candidates
- multi-person reference
- batch input
- interrupt running
- sequential layering
- supported layer roles
- preserve existing garments
- outfit context
- region mask
- input format/size limits
- output limits

每个能力包含：

- `supported`
- `source`: `adapter | workflow_declared | derived`
- `verification`: `verified | declared | unavailable`
- 可选安全说明

顶层包含 `schema_version`，允许后续添加能力而不改变既有字段语义。

## Tasks

### Task 1 — Initialize repository and architecture records

Affected:

- Repository root
- `.gitignore`
- `.editorconfig`
- `README.md`
- `docs/adr/`

Work:

- 初始化 Git，默认分支 `main`。
- 保留现有 specs、prototypes 和 `DESIGN.md`。
- 建立目标顶级目录和 ownership 说明。
- 记录五项 ADR。
- 固化 generated code、lockfile、环境文件和 build artifacts 的 Git 策略。
- 在 README 中声明 Phase 1 scope 和 Phase 2–9 非目标。

Dependencies:

- 无。

Verify:

- `git rev-parse --is-inside-work-tree` 成功。
- Git 能追踪规格和工程文件，不追踪 `.env`、build、IDE、数据库和上传内容。
- ADR 状态为 `Accepted`，且彼此不矛盾。

### Task 2 — Establish the shared OpenAPI contract

Affected:

- `contracts/openapi/`
- `contracts/tooling/`

Work:

- 建立 OpenAPI 3.0.3 多文件结构。
- 定义统一 ID、时间、分页、错误、幂等和 version reference schema。
- 定义 V1 的 Auth、Uploads、Assets、Jobs、JobItems、Outputs、Providers、Capabilities、Workflows、Admin Configuration、Storage、Diagnostics 资源边界。
- 固化 Job、JobItem、Workflow 和配置状态枚举。
- 加入代表性成功、等待、部分成功、`needs_attention`、权限错误和存储阻塞 examples。
- 只定义后续实现必须共享的 contract shape；业务 endpoint 可以保留明确的 stub/未实现响应。

Dependencies:

- Task 1 ADR 决策。

Verify:

- OpenAPI lint 通过。
- 所有 `$ref` 可解析并生成单一 bundled spec。
- mock server 可从 bundled spec 启动。
- 契约中不存在 V1.1 `Outfits` API。
- Android/Web 不需要自行补充任务状态、错误结构或 capability 字段。

### Task 3 — Build the Backend engineering skeleton

Affected:

- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/src/clothes_model/`
- `backend/tests/`

Work:

- 建立 FastAPI application factory、生命周期、route registry 和模块化单体包。
- 配置 Pydantic Settings 与 `.env` 开发读取。
- 建立结构化日志、trace/request ID 和统一 Problem Details handler。
- 实现 `/health/live` 和 `/health/ready`。
- 建立各资源的 route stub；不得加入正式认证、素材、任务或 Provider 逻辑。
- 接入生成的 Backend contract models。
- 明确模块依赖方向，禁止 domain/application 反向依赖 FastAPI 或 SQLite。

Dependencies:

- Task 2 的 contract schemas。

Verify:

- `uv sync --locked`、Ruff、Pyright、Pytest 全部通过。
- Backend clean start。
- live/ready endpoint 返回约定结构。
- 未实现 route 返回统一的 safe problem response，不返回临时自由格式 JSON。
- 日志中没有环境 Secret 值。

### Task 4 — Establish database, migrations, and scheduler boundaries

Affected:

- `backend/src/clothes_model/infrastructure/database/`
- `backend/src/clothes_model/infrastructure/scheduler/`
- `backend/migrations/`
- Backend migration and runtime tests

Work:

- 建立 SQLAlchemy async engine、session、Unit of Work 和 repository interface。
- 配置 SQLite foreign keys、WAL、busy timeout 和事务边界。
- 初始化 Alembic。
- 创建仅用于验证 migration 机制的基础 revision；不提前建立 Phase 2–9 业务表。
- 建立 scheduler lifecycle port、fake scheduler 和 no-op job source。
- 建立 production single-instance lock。
- Scheduler 不得执行真实业务任务。

Dependencies:

- Task 3 Backend lifecycle 和 config。

Verify:

- 空 SQLite 文件可 `upgrade head`。
- migration 可在临时数据库重复运行。
- rollback/upgrade smoke test 通过。
- 两个启用 scheduler 的进程指向同一数据目录时，第二个进程 fail fast。
- scheduler 关闭时可运行 API/tests。

### Task 5 — Generate clients and validate contract consumption

Affected:

- `contracts/tooling/`
- `backend/.../generated/`
- `android/core/api-contract/`
- `web-admin/src/api/generated/`

Work:

- 锁定 OpenAPI lint、bundle、mock 和 generator 版本。
- 生成 Backend data models、Android client、Web types/client。
- 添加统一 regenerate 命令和 generated header。
- 添加 CI drift check。
- 配置 mock server 的 authentication placeholders 和代表性 examples。
- 验证 unknown enum/error fallback 策略。

Dependencies:

- Tasks 2–4。

Verify:

- 在干净环境中可重新生成全部 artifacts。
- 再次生成后 `git diff` 为空。
- 三个生成目标均编译。
- mock server 能返回 job、provider capabilities、storage 和 diagnostics examples。

### Task 6 — Build the Web Admin skeleton

Affected:

- `web-admin/`
- Root pnpm workspace and lockfile

Work:

- 建立 React/TypeScript/Vite 工程。
- 建立 router、application shell、error boundary、query client 和配置入口。
- 建立 API client adapter，生成代码不直接泄漏到页面组件。
- 添加 contract-status/debug route，通过 mock API 展示 health、JobState、capability sample。
- 只建立工程和 contract proof，不实施 A00–A12 正式管理页面。
- 添加 lint、typecheck、unit test 和 production build。

Dependencies:

- Task 5 Web client 和 mock server。

Verify:

- frozen lockfile install 成功。
- lint、typecheck、test、build 通过。
- Playwright 能启动 Web + mock 并读取示例契约。
- production bundle 不包含 token、开发 `.env` 或 mock credentials。

### Task 7 — Build the Android skeleton

Affected:

- `android/`
- `android/app/`
- `android/core/api-contract/`

Work:

- 建立 Gradle Kotlin DSL、version catalog 和 wrapper。
- 建立 Compose Material 3 application shell。
- 建立 DI、navigation placeholder 和 debug-only endpoint configuration。
- 封装 generated client，向 app 暴露稳定 repository/gateway boundary。
- 建立 contract status screen，通过 mock API 读取 health、任务状态和 capability sample。
- 不实现认证、上传、素材库、任务创建或正式 UI flow。
- 建立 unit、lint 和 Compose test baseline。

Dependencies:

- Task 5 Android client 和 mock server。

Verify:

- `assembleDebug`、Android lint、unit tests 通过。
- generated client 单独编译。
- emulator/manual smoke 可连接 mock。
- release variant 不包含开发地址、测试 Token 或 mock 配置。

### Task 8 — Establish local development and V1 deployment skeleton

Affected:

- `infra/compose.yaml`
- `infra/Caddyfile`
- `infra/docker/`
- `.env.example`
- `README.md`

Work:

- 建立 contract-mock、backend、production app 和 Caddy 的 Compose profiles。
- 使用 multi-stage build 构建 Web Admin，并由固定服务器部署单元托管。
- 配置 SQLite、private storage 和 instance lock 持久卷。
- 写明本地 Web、Android emulator、Backend、mock 的启动矩阵。
- 配置明确的 dev CORS allowlist。
- 生产 entrypoint 在启动服务前执行 Alembic upgrade。
- 固定 application replica=1、Uvicorn worker=1、scheduler owner=1。

Dependencies:

- Tasks 3、4、6、7。

Verify:

- 容器镜像可以 clean build。
- Compose 启动后 HTTPS/本地代理路由到 Backend health 和 Web shell。
- 重启 application container 后 SQLite 文件仍存在。
- 尝试启动第二个 scheduler owner 明确失败。
- production profile 不包含 mock server。

### Task 9 — Establish CI and quality gates

Affected:

- `.github/workflows/ci.yml`
- 各工程 lint/test/build 配置
- README verification commands

Work:

- 建立 contract、backend、web、android、deployment jobs。
- 使用缓存但不缓存工作区生成结果作为真源。
- 强制 frozen/locked dependency install。
- 执行 contract generation drift check。
- 上传测试报告和构建日志，不上传 Secret 或私有数据。
- 配置 job cancellation/concurrency，避免旧提交占用资源。
- 增加依赖和 runtime 版本输出，方便复现。

Dependencies:

- Tasks 2–8。

Verify:

- CI 从空缓存运行成功。
- 任一 contract drift、lint error、type error、test failure 或 build failure 能阻止合并。
- Android、Backend、Web jobs 可并行。
- deployment smoke 只在三个 build job 成功后运行。

### Task 10 — Run the integrated Phase 1 exit gate

Affected:

- README Phase 1 verification section
- Contract test fixtures
- Cross-application smoke tests

Work:

- 从 clean checkout 按文档安装工具链。
- 重新生成契约 artifacts。
- 完成 Backend、Android、Web clean build。
- 启动 contract mock，验证 Android/Web 的消费边界。
- 启动 Backend，验证 health、configuration failure 和 Problem Details。
- 启动 production Compose profile，验证反向代理、持久卷和 single-instance guard。
- 核对 ADR、环境模板和单实例约束。
- 记录实际命令和已知开发环境限制。

Dependencies:

- Tasks 1–9。

Verify:

- Phase Exit Checklist 全部通过。
- 不依赖本机未记录的全局包、Secret 或 IDE 状态。
- 仓库中没有 Phase 2 认证、业务 schema、文件系统或任务执行实现。

## Phase Exit Checklist

### Repository

- [x] Git repository 已初始化，默认分支为 `main`
- [x] 现有 specs、flow、UI specs、DESIGN 和 prototypes 已保留
- [x] Monorepo 顶级目录与 ownership 清晰
- [x] README 包含 clean setup 和验证命令
- [x] `.gitignore` 不允许 Secret、数据库、上传文件或 build artifacts 入库

### Contracts

- [x] OpenAPI lint、bundle、reference validation 通过
- [x] 共享任务状态和 JobItem 状态已固化
- [x] Problem Details error model 已固化
- [x] cursor pagination 已固化
- [x] idempotency convention 已固化
- [x] Provider/Workflow version references 已固化
- [x] capability representation 已固化
- [x] Android/Web/Backend generated artifacts 无 drift
- [x] contract mock 可启动
- [x] 契约未提前加入 V1.1 Outfits API

### Backend

- [x] Backend clean dependency sync
- [x] Ruff、Pyright、Pytest 通过
- [x] Backend clean build/start
- [x] `/health/live` 可用
- [x] `/health/ready` 可用并检查基础依赖
- [x] Problem responses 与 contract 一致
- [x] Alembic 可从空数据库升级
- [x] migration smoke test 通过
- [x] no-op scheduler 生命周期可测试
- [x] 第二实例不能取得 scheduler ownership

### Android

- [x] Gradle wrapper 和 version catalog 已提交
- [x] Android clean `assembleDebug`
- [x] Android lint 通过
- [x] JVM unit-test baseline 通过
- [x] Compose test infrastructure 可用
- [x] generated API client 编译
- [x] debug app 能消费 contract mock
- [x] release artifact 不包含开发 URL 或测试 Secret

### Web Admin

- [x] frozen pnpm install 成功
- [x] ESLint、TypeScript、Vitest 通过
- [x] production build 成功
- [x] generated API client 编译
- [x] Web shell 能消费 contract mock
- [x] browser smoke test 通过
- [x] bundle 不包含 Secret 或 mock credentials

### CI and deployment

- [x] GitHub Actions contract/backend/web/android jobs 可运行
- [x] CI 使用 lockfile/frozen installs
- [x] container clean build
- [x] production Compose profile 可启动
- [x] Caddy 能路由 Web 和 Backend health
- [x] SQLite/private storage 使用持久卷
- [x] `.env.example` 完整且不含真实 Secret
- [x] production secret injection boundary 已记录
- [x] V1 replica=1、worker=1、scheduler=1 已在配置和 ADR 中同时记录
- [x] 第二 application/scheduler instance fail fast
- [x] 未引入 Redis、Kafka、PostgreSQL、Kubernetes 或独立 Worker

### Documentation

- [x] 五项 ADR 全部 accepted
- [x] Backend module dependency direction 已记录
- [x] OpenAPI ownership和生成流程已记录
- [x] 本地 mock/backend/web/android 启动方式已记录
- [x] V1 single-instance 升级限制已记录
- [x] Phase 1 明确不包含 Phase 2–9 实现

## Risks

- OpenAPI generator 对 Kotlin 的输出质量可能不完全符合预期。Task 5 必须先完成生成与编译 spike；若生成的 transport client 不稳定，保留生成 DTO/API interfaces，手写薄 transport adapter，但不能复制 contract models。
- Python 3.14 较新。Task 3 必须在锁依赖前验证 FastAPI、Pydantic、SQLAlchemy、Alembic 和测试工具全部支持；失败时允许技术性降级到 Python 3.13，并更新 ADR。
- Android 工具链下载量较大。CI 应缓存 Gradle 和 Android SDK，但 clean build 仍必须能从空缓存成功。
- SQLite + async API 不会提升 SQLite 本身的并发写能力。V1 依靠单实例、短事务、WAL 和有限调度并发，而不是假设数据库可水平扩展。
- 提交 generated code 会产生 diff 噪音，但能避免 Android clean build 依赖额外 Node/Docker 环境；CI drift check 保证其不是第二真源。
- Phase 1 contract 如果过度展开，容易提前设计 Phase 2–9。每个 resource 只定义跨端必须共享的 identity、state、commands、references 和 error boundary。

## Upstream Conflicts

无阻塞性的 `Upstream Conflict`。

需要记录但不需要回到产品阶段的技术解释：

- Product Flow 的 `needs_attention → running` 是主任务聚合状态变化；Product Spec 明确要求人工重试创建新的可追踪 JobItem，因此不得把原 JobItem 或原 external execution 覆盖为 `running`。
- `partially_succeeded` 只适用于 `TryOnJob` 聚合，不适用于单个 `JobItem`。
- V1 的 `person_asset_ids` 仍保持数组形态，但本阶段不实现 V1.1 多人物、Outfits、分层角色或会话 API。

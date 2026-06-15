# SmartClass Agent `AGENTS.md`

## 1. 文档定位

本文件是仓库根目录的主规范，帮助 AI：

- 准确理解项目当前真实状态，而不是把 roadmap 当成已实现能力
- 在前后端、Agent、RAG、文件处理、对象存储、长期记忆、认证权限、产物生成与工程化治理之间保持一致的数据契约
- 优先做高价值、低歧义、可验证、可回滚的改动，减少返工和错误假设
- 在后续 Agent 增强中优先考虑稳定性、安全性、可观测性与评估闭环

由于沙盒环境和路径问题，读取代码时优先使用绝对路径。

## 2. 项目定位与当前阶段

SmartClass 是一个面向教师的多模态互动式教学智能体，目标是帮助老师完成备课、教学设计、教案生成、PPT 生成、互动内容生成与产物迭代修改。

当前项目已经从“主流程功能建设阶段”进入“Agent Harness 治理与工程化增强阶段”。

当前真实状态：

- 产品主流程已经基本打通：登录、聊天、教学设计、知识库 RAG、附件分析、语音/视频输入、产物生成、产物预览、产物差量修改都已具备实现
- 后端接口大多已要求登录态，计划、会话、知识库文件、附件、产物通过 `user_id` 进行归属过滤
- 文件链路已经通过 `StorageService` 写入稳定 `storage_key`，数据库仍保留 `storage_path` 以兼容历史本地文件
- LangGraph 已接入长期记忆：先加载用户画像，再按当前请求选择相关经验，结束后反思并写入画像/经验记忆
- 可观测性已初步落地：后端有统一 `RunContext`、`ObservationSink`、结构化日志、可选 JSONL trace、OpenTelemetry OTLP 导出与 Prometheus `/metrics` 导出能力
- Agent 评估系统已初步落地在 `backend/tests/evals/`，覆盖意图识别、记忆检索/写入/更新、教学要素抽取等评估用例与运行器
- 后续重点不再是简单堆功能，而是提升 Agent 行为的可控性、稳定性、安全性、可观测性与可评估性

## 3. 当前技术栈与事实入口

### 后端

- FastAPI
- LangChain
- LangGraph
- PostgreSQL
- SQLAlchemy
- PGVector 风格 RAG
- LangGraph PostgreSQL checkpointer 与 store
- OpenAI 兼容模型接口
- JWT Bearer 认证
- MinIO 对象存储兼容本地存储 与 Agent workspace
- OpenTelemetry / Prometheus 可选观测导出
- Agent evaluation harness

关键事实入口：

- [`backend/app/main.py`](./backend/app/main.py)
- [`backend/app/config.py`](./backend/app/config.py)
- [`backend/app/dependencies/db.py`](./backend/app/dependencies/db.py)
- [`backend/app/core/graph.py`](./backend/app/core/graph.py)
- [`backend/app/core/agent.py`](./backend/app/core/agent.py)
- [`backend/app/core/auth.py`](./backend/app/core/auth.py)
- [`backend/app/core/memory.py`](./backend/app/core/memory.py)
- [`backend/app/core/storage.py`](./backend/app/core/storage.py)
- [`backend/app/core/skills.py`](./backend/app/core/skills.py)
- [`backend/app/core/workspace.py`](./backend/app/core/workspace.py)
- [`backend/app/core/progress.py`](./backend/app/core/progress.py)
- [`backend/app/core/rag.py`](./backend/app/core/rag.py)
- [`backend/app/core/observability.py`](./backend/app/core/observability.py)
- [`backend/app/core/observability_bootstrap.py`](./backend/app/core/observability_bootstrap.py)
- [`backend/app/core/evaluation.py`](./backend/app/core/evaluation.py)
- [`backend/app/models/user.py`](./backend/app/models/user.py)
- [`backend/app/models/file.py`](./backend/app/models/file.py)
- [`backend/app/services/auth_service.py`](./backend/app/services/auth_service.py)
- [`backend/app/services/file_service.py`](./backend/app/services/file_service.py)
- [`backend/app/services/artifact_service.py`](./backend/app/services/artifact_service.py)
- [`backend/app/api/auth.py`](./backend/app/api/auth.py)
- [`backend/app/api/chat.py`](./backend/app/api/chat.py)
- [`backend/app/api/file.py`](./backend/app/api/file.py)
- [`backend/app/api/memory.py`](./backend/app/api/memory.py)
- [`backend/app/schemas/auth.py`](./backend/app/schemas/auth.py)
- [`backend/app/schemas/memory.py`](./backend/app/schemas/memory.py)
- [`backend/tests/evals/`](./backend/tests/evals/)
- [`docs/observability/`](./docs/observability/)

### 前端

- Vue 3
- Vite
- Element Plus
- shadcn/ui
- Pinia
- OnlyOffice 文档预览
- SSE 流式聊天与 Agent 进度/产物事件消费

关键事实入口：

- [`frontend/src/api/index.js`](./frontend/src/api/index.js)
- [`frontend/src/api/auth.js`](./frontend/src/api/auth.js)
- [`frontend/src/api/memory.js`](./frontend/src/api/memory.js)
- [`frontend/src/api/file.js`](./frontend/src/api/file.js)
- [`frontend/src/store/user.js`](./frontend/src/store/user.js)
- [`frontend/src/components/AuthDialog.vue`](./frontend/src/components/AuthDialog.vue)
- [`frontend/src/components/ChatPanel/index.vue`](./frontend/src/components/ChatPanel/index.vue)
- [`frontend/src/components/ContextPanel/index.vue`](./frontend/src/components/ContextPanel/index.vue)
- [`frontend/src/components/FilePreviewPanel/index.vue`](./frontend/src/components/FilePreviewPanel/index.vue)
- [`frontend/vite.config.js`](./frontend/vite.config.js)

## 4. 仓库结构速览

```text
demo/
├─ backend/
│  ├─ app/
│  │  ├─ api/          # auth / chat / file / memory / plan / session 接口
│  │  ├─ core/         # graph、agent、auth、memory、storage、rag、skills、llm、progress、workspace、observability、evaluation
│  │  ├─ models/       # SQLAlchemy 模型
│  │  ├─ schemas/      # API schema
│  │  └─ services/     # 业务逻辑
│  ├─ skills/          # docx / pdf / ppt-generator / html-interactive 等 skills
│  ├─ storage/         # 本地存储兼容根目录、上传文件、附件、产物与 agent workspace
│  └─ tests/
│     └─ evals/        # Agent 评估用例、评估器、运行器与结果
├─ docs/
│  └─ observability/   # OTel Collector / Prometheus 本地接入示例
├─ frontend/
│  ├─ src/
│  │  ├─ api/
│  │  ├─ components/
│  │  ├─ layout/
│  │  ├─ router/
│  │  └─ store/
│  └─ AGENTS.md
├─ landing-page/
└─ openspec/
```

## 5. 当前能力矩阵

### 已实现

- 用户注册、登录、获取当前用户：
  - `/api/auth/register`
  - `/api/auth/login`
  - `/api/auth/me`
- JWT Bearer 登录态校验，下载、预览、OnlyOffice 回调等场景支持 Authorization header 或 `access_token` 查询参数
- 教学计划、会话、知识库文件、附件、产物文件的基础 CRUD 与查询接口
- 计划、会话、知识库文件、附件、产物通过 `user_id` 做资源归属过滤
- LangGraph 主流程：
  - 意图识别
  - 长期记忆加载与相关经验选择
  - 教学要素抽取
  - 信息不完整时追问并中断
  - 教学要素确认与教学设计确认
  - RAG 向量检索
  - 教学设计规划输出
  - 产物生成路由
  - 产物修改路由与目标澄清
  - 对话结束后的长期记忆反思写入
- 长期记忆体系：
  - `profile` 用户画像/偏好记忆
  - `experience` 可复用教学经验记忆
  - 按用户命名空间隔离：`("users", user_id, "profile")` 与 `("users", user_id, "experiences")`
  - `/api/memory` 支持列表、创建、更新、删除
  - 普通聊天、教学规划、产物修改链路都会加载可用记忆
- 附件分析入口，附件会通过 agent + skills 做文档分析
- 语音输入转写与视频附件分析
- Skill registry 与 progressive disclosure 风格 skill 加载
- Agent workspace 工具：
  - 列文件
  - 读写 UTF-8 文本文件
  - 精确替换文本
  - 运行受限 Python / Node 代码
- 初步 Agent 执行约束：
  - workspace 路径穿越防护
  - workspace 执行超时与输出截断
  - 禁止 workspace 代码安装依赖
  - SkillExecutionPolicyMiddleware 限制部分工具必须由 active skill 授权
  - shell 中阻断 Python / Node / npm / pip 等应走 workspace 的执行方式
  - ToolRetryMiddleware 已接入工具重试
- 知识库文件异步入库链路
- 对象存储抽象：
  - `StorageBackend` / `StorageService`
  - `StoredObject`
  - 本地后端 `LocalStorageBackend`
  - MinIO 兼容后端 `MinioStorageBackend`
  - 稳定 `storage_key`
  - 可选预签名下载
- 知识库、附件、产物上传/生成/下载已接入 `StorageService`
- 前端登录状态持久化到 `localStorage`
- 前端 Axios 自动附加 `Authorization: Bearer <token>`
- 前端遇到 401 会清理登录态并广播 `smartclass-unauthorized`
- 前端聊天已接入 SSE 流式响应
- 后端驱动的流程进度卡片
- 前端 AI 消息 Markdown 实时渲染
- 前端附件上传能力
- OnlyOffice 预览与回写知识库/产物文件
- 统一 artifact 产物模型已落地到 `ArtifactFile` 与 `artifact_service`
- 产物生成闭环：
  - PPT
  - DOCX 教案
  - HTML 互动内容
- 产物生成流程前端可视化
- 产物 revision 历史与当前版本标记
- HTML 互动内容后端预览页，iframe 使用 sandbox 限制
- Agent 运行中可发出 `artifact_trace`，用于展示产物子 Agent 的执行轨迹
- 审批中断与恢复：
  - 教学要素确认
  - 教学计划确认
  - 产物修改目标确认
- 对话后续建议 `suggestions`
- 统一可观测性基础设施：
  - `RunContext` 贯穿 `run_id`、`thread_id`、`plan_id`、`user_id`、`agent_name`
  - `ObservationSink` 支持结构化 logging、可选 JSONL trace、OpenTelemetry span、Prometheus metrics
  - `trace_span()`、`record_metric()`、`log_observation()` 与 `observe_llm_call()` 用于记录 span、指标、错误分类和 token usage
  - `configure_external_observability(app)` 在 FastAPI 启动时按配置接入 OTEL 与 Prometheus
  - Prometheus 可通过 `/metrics` 暴露低基数指标，Grafana 可基于 Prometheus 或 OTel Collector 后端配置仪表盘
  - `docs/observability/otel-collector.yaml` 与 `docs/observability/prometheus.yml` 提供本地接入示例
- Agent 评估系统：
  - `backend/app/core/evaluation.py` 定义 `EvalCase`、`EvalAssertion`、`EvalResult`、`EvalReport`
  - `backend/tests/evals/cases/` 存放 YAML 评估用例
  - `backend/tests/evals/evaluators/` 已有 intent、memory、extraction 评估器
  - `backend/tests/evals/runners/eval_runner.py` 汇总运行评估并生成 JSON report
  - `backend/tests/evals/cli.py` 支持 `list-categories`、`validate`、`run` 等命令，结果写入 `backend/tests/evals/results/`

### 已有但需要加强

- 长期记忆已接入 graph，但仍需加强：
  - 记忆写入、更新、删除还需要更明确的审计、用户可见解释与评估集
  - 记忆内容应避免保存完整隐私上下文
- Agent 护栏已有基础 middleware 与 workspace 限制，但尚未形成完整策略体系
- 可观测性已有基础框架，但仍需扩大关键链路覆盖率、补足运行摘要、失败归因、Grafana dashboard 与告警规则
- 评估系统已具备初步 harness 与用例集，但仍需持续沉淀回归样本，扩展 RAG、产物生成/修改、安全性、性能等评估维度，并接入自动化质量门禁

## 6. 当前真实数据流

### 6.1 登录与权限链路

1. 用户通过 `/api/auth/register` 注册教师账号，通过 `/api/auth/login` 登录，后端校验 PBKDF2-SHA256 密码哈希。
3. 登录成功后后端签发 HS256 JWT，payload 至少包含 `sub`、`username`、`role`、`exp`。
6. 后端接口通过 `get_current_user` 或 `get_current_user_from_auth_or_query` 获取当前用户。
7. 计划、会话、知识库文件、附件、产物查询和修改都应带上 `current_user.id` 做归属过滤。
8. 文件下载、HTML 预览、OnlyOffice 配置/回调等需要浏览器或第三方服务访问的链路，可用查询参数传递 `access_token`。

### 6.2 对话主链路

1. 前端通过 `/api/chat/stream` 发起请求，请求必须处于登录态。
2. 后端创建 `run_id`，先发送 `metadata` SSE 事件。
3. 后端根据 `thread_id` 与 `current_user.id` 找到会话与 `plan_id`。
4. 如果请求携带 `attachment_ids`，先按当前用户、当前 plan/thread 解析附件并生成 `attachment_text`。
5. LangGraph 使用当前 `user_id` 作为 runtime context：
   - 先加载 profile 记忆
   - 再根据意图选择 experience 记忆
6. LangGraph 根据当前状态进入：
   - 普通聊天
   - 教学规划主流程
   - 产物修改流程
   - 审批中断恢复
7. 运行期间通过 SSE 推送 token、进度、产物、产物 trace、审批请求、错误等事件。
8. 节点结束后进入 profile/experience 记忆反思节点，按需要创建或更新长期记忆。
9. 结束时发送 `done`。

当前后端实际支持的 SSE 事件：

- `metadata`
- `token`
- `progress`
- `artifact`
- `artifact_trace`
- `approval`
- `suggestions`
- `error`
- `done`

### 6.3 长期记忆链路

1. Agent runtime 初始化时创建 LangGraph memory store。
2. `profile_memory_load_node` 从当前用户 profile namespace 拉取画像和偏好。
3. intent route 之后，根据当前任务进入对应的 memory retrieval node。
4. experience selector 从最多 100 条经验摘要中选择最多 3 条相关经验。
5. 选中的 profile/experience 记忆以 system message 形式注入后续 LLM 调用。
6. 普通聊天、教学设计、追问、产物修改等节点可使用记忆上下文，但当前显式用户指令优先。
7. 对话或阶段结束后，反思节点根据最近对话创建或更新 profile/experience 记忆。
8. 用户也可以通过 `/api/memory` 对自己的记忆做 CRUD。

### 6.4 知识库文件链路

1. 上传到 `knowledge_files`，并绑定 `user_id` 与 `plan_id`。
2. `file_service` 生成稳定 `storage_key`，通过 `StorageService` 写入当前配置的存储后端。
3. 数据库记录 `storage_backend`、`storage_key`、`storage_path`、sha256、状态等字段。
4. 后端异步入队。
5. `FileIngestionRuntime` 消费队列。
6. RAG runtime 通过 `materialize_knowledge_file` 获取本地临时路径，再做解析、切分、向量化与入库。
7. 前端轮询知识库文件状态并展示“待解析 / 特征解析中 / 已解析 / 失败”。
8. 删除知识库文件时先删除 RAG 文档，再标记 deleted，并删除存储对象。

### 6.5 会话附件链路

1. 上传到 `attachment_files`，并绑定 `user_id`、`plan_id`、`thread_id`。
2. `file_service` 生成稳定 `storage_key`，通过 `StorageService` 写入当前配置的存储后端。
3. 发送消息时携带 `attachment_ids`。
4. 后端按 `user_id + plan_id + thread_id + attachment_ids` 校验归属。
5. 后端先做附件分析，再把摘要注入图输入。
6. 语音与视频附件有专门的转写/分析链路。

### 6.6 产物链路

1. 教学计划经用户确认后，可选择生成 `ppt`、`docx`、`html-game`。
2. 后端为每个产物创建 running 状态的 `ArtifactFile`，并绑定 `user_id`、`plan_id`、`thread_id`。
3. 产物子 Agent 在 workspace 中执行 skill 或代码工具。
4. 生成结果通过 `artifact_service.mark_artifact_ready` 写入 `StorageService`。
5. 产物状态更新为 `ready` 或 `failed`，并通过 SSE `artifact` 事件推给前端。
6. 产物修改会基于源产物创建 revision，并维护 `parent_artifact_id`、`root_artifact_id`、`revision_number`、`is_current`。
7. 下载、OnlyOffice 配置、HTML 预览都通过当前用户校验后读取存储对象。

### 6.7 可观测性与评估链路

1. `/api/chat/stream` 创建 `run_id` 后构造 `RunContext`，并把 `run_id` 放入 `metadata` SSE 事件。
2. Agent、graph、LLM、workspace、RAG、storage、artifact 等关键链路可通过 `trace_span()`、`record_metric()`、`log_observation()` 或 `observe_llm_call()` 发出工程观测事件。
3. `ObservationSink` 默认输出结构化日志；开启 `OBSERVABILITY_TRACE_JSONL_ENABLED=true` 时写入本地 JSONL trace，默认目录在 `backend/storage/observability/traces/`。
4. 开启 `OTEL_ENABLED=true` 且配置 `OTEL_EXPORTER_OTLP_ENDPOINT` 后，后端通过 OTLP HTTP 导出 FastAPI request trace 与 SmartClass observation span。建议经 `docs/observability/otel-collector.yaml` 转发到 Tempo、Jaeger、Grafana Cloud 等后端。
5. 开启 `PROMETHEUS_ENABLED=true` 后，FastAPI 暴露 `PROMETHEUS_METRICS_PATH`，默认 `/metrics`，`docs/observability/prometheus.yml` 提供本地 scrape 示例。
6. 观测字段会经过脱敏与截断，不应记录完整 prompt、completion、附件正文、RAG chunk、长期记忆正文、JWT、Authorization header、预签名 URL 签名、对象 key 或宿主机路径。
7. Prometheus label 必须保持低基数，不应把 `run_id`、`thread_id`、`user_id`、文件名、对象 key、URL 等高基数字段作为 label。
8. 评估系统位于 `backend/tests/evals/`，用 YAML case 描述输入、上下文、期望和断言，由 intent、memory、extraction 等 evaluator 执行，runner 汇总为 `EvalReport` 并保存到 `results/`。
9. 运行评估通常需要数据库、模型 API 与相关环境变量；CLI 默认关闭 Prometheus 和 observability，避免评估过程污染本地观测出口。

## 7. 下一阶段开发重点

### 7.1 Agent 护栏与治理

后续新增 Agent 能力时，优先把它纳入可治理框架，而不是只追加 prompt 或工具。

优先方向：

- 明确每类 Agent 的职责边界：主流程 Agent、附件分析 Agent、产物生成 Agent、产物修改 Agent、记忆反思 Agent、评估 Agent
- 统一工具调用审计字段：`run_id`、`thread_id`、`plan_id`、`user_id`、`agent_name`、`tool_name`、输入摘要、输出摘要、耗时、状态、错误
- 对模型输出做结构化校验，关键节点优先使用 Pydantic/schema 验证
- 对 Agent 失败做可分类的错误建模：模型错误、工具错误、权限错误、用户输入不足、文件处理失败、存储失败、记忆失败、超时、外部服务失败
- 保留 human-in-the-loop，不要为了自动化绕过确认节点

### 7.2 评估闭环

后续优先扩展的评估维度：

- 追问质量：信息不足时是否问关键缺口，而不是过度追问
- RAG 质量：检索内容是否相关、是否被正确引用到教学设计
- 产物生成成功率：是否产出合法文件、文件是否可打开、是否与教学计划一致
- 产物修改准确率：是否改对目标产物、是否保留未要求修改的内容
- 安全性：是否拒绝越权文件访问、危险命令、未授权工具使用
- 稳定性：超时、重试、失败状态是否可追踪且前端可见

### 7.3 工程化增强

后续工程化优先级：

- 日志系统：
  - 从零散 `print` 迁移到结构化 logging
  - 日志必须带 `run_id`、`thread_id`、`plan_id`、`user_id`，必要时带 `artifact_id`
  - 避免记录完整用户隐私内容、完整附件内容、完整模型上下文、JWT 明文
- 可观测性：
  - 已有 `backend/app/core/observability.py`，统一记录 Agent 节点耗时、工具耗时、RAG/存储/产物等事件、失败类型与 token 使用
  - 已有 `backend/app/core/observability_bootstrap.py`，按配置接入 OpenTelemetry 与 Prometheus；`backend/app/main.py` 已调用 `configure_external_observability(app)`
  - OTEL 与 Prometheus 必须保持可选，不把 Tempo、Jaeger、Grafana Cloud、Datadog、LangSmith 等第三方平台写死进核心业务
  - Grafana 建议通过 Prometheus scrape 或 OTel Collector 后端数据源配置，不应由业务代码直接耦合 dashboard 平台
  - 继续为 SSE 生命周期、文件入库、产物生成、OnlyOffice 回调等补齐可追踪事件、运行摘要和失败归因
- 后台任务：
  - 文件入库、视频分析、产物生成等长任务应逐步具备任务状态、重试、取消与幂等能力
- 配置治理：
  - 所有模型、存储、日志、外部服务、JWT 密钥、默认账号配置必须来自配置层或环境变量
  - 不在业务代码中硬编码本地机器路径、外部地址、密钥或生产默认密码

## 8. 关键现实约束

### 8.1 模型与 skill 约束

- 当前后端实际模型封装在 [`backend/app/core/llm.py`](./backend/app/core/llm.py)，使用 OpenAI 兼容接口
- skill 风格参考 progressive disclosure，但运行时不是 Anthropic SDK
- AI 不要把“Anthropic 风格 skill 文档”误判为“Anthropic 模型运行时”
- 涉及 Office、PDF、PPT 的处理优先复用现有 skill/script，而不是直接让模型裸处理二进制内容

### 8.2 认证与权限约束

- 后端资源归属的事实依据是数据库 `user_id`，不是前端传来的用户字段
- 注册登录是教师自助注册 + 默认 admin 兼容账号，当前不是完整组织/班级/学校多租户体系
- `role`、`is_superuser` 已存在，但没有完整 RBAC 策略时不要假设某个角色拥有额外权限
- 所有新增资源模型若属于用户私有数据，必须添加或继承 `user_id` 归属关系
- 所有跨资源操作必须同时校验 `user_id` 和业务上下文，例如 `plan_id`、`thread_id`、`artifact_id`

### 8.3 长期记忆约束

- 长期记忆属于用户级上下文，不属于某个单独 thread 的短期聊天历史
- profile 记忆用于稳定画像、偏好、明确要求记住的内容
- experience 记忆用于可复用教学经验、策略、工作流观察和产物经验
- 记忆内容应做摘要化、最小化和可解释化，不保存完整敏感上下文

### 8.4 文件与存储约束

- `knowledge_files`、`attachment_files`、`artifact_files` 是三条不同链路
- `knowledge_files` 面向知识库和 RAG
- `attachment_files` 面向单次或多轮会话上下文分析
- `artifact_files` 面向 Agent 生成和修改后的用户可见产物
- 任何新增多模态能力都必须先明确属于哪条链路，不能混用
- 新增文件读写必须通过 `StorageService`
- 不要在业务代码里继续散落 `Path(storage_path)` 直接读写
- 数据库可继续保留 `storage_path` 以兼容当前实现，但新增代码应优先通过 `storage_backend + storage_key` 访问
- 对象存储后端不保证存在长期本地路径；需要本地文件时使用 `materialize_temp_file`
- URL 生成、预签名、下载策略不应散落在业务逻辑中

### 8.5 Agent workspace 约束

- workspace 是 Agent 产物生成与 skill 执行的受控工作区，不等同于项目源码目录
- Agent workspace 工具只能访问当前 thread/run 下的 workspace 路径
- workspace 代码执行已有超时、输出截断与安装命令限制；新增执行能力必须继承这些约束
- 不允许通过 shell 绕过 workspace 工具策略
- 产物子 Agent 输出必须最终进入 artifact 链路，不应只停留在临时 workspace

### 8.6 平台与工具约束

- 当前项目运行环境对 Windows 友好
- Shell、路径、OnlyOffice 接入都应保持 Windows 兼容
- 不要默认依赖 Linux-only 的处理方式
- 文件路径展示、存储 key、URL 查询参数要考虑 Windows 分隔符和跨平台序列化

### 8.7 Git 与工作区约束

- 提交前先确认当前 git 根目录与工作区状态
- 不要假设这是一个绝对干净、单一边界的 monorepo
- 前后端目录作为子模块显示修改状态
- 不要回滚用户已有改动，除非用户明确要求

### 8.8 编码与文本约束

- 文本、提示词、文档默认使用 UTF-8
- 如果出现中文乱码，优先处理编码问题，不要在乱码文本上继续堆功能

## 9. AI 开发原则

- 先补数据契约，再补 UI 细节
- 先做权限归属校验，再做业务操作
- 先做垂直切片，再做大范围重构
- 不把 roadmap feature 当成已存在接口
- Agent 能力优先纳入权限、状态、日志、评估四个维度
- 对长链路任务优先保证可恢复、可追踪、可失败，而不是假装一定成功
- 对外部依赖和本地环境差异要显式建模，不靠隐式机器状态
- 新增抽象必须能消除真实重复或隔离真实变化点，避免为了“架构感”过度设计

## 10. 稳定契约

以下契约是后续开发默认遵循的稳定方向。新增实现时优先兼容这些约定。

### 10.1 SSE 事件契约

当前及目标事件类型：

- `metadata`
- `token`
- `progress`
- `artifact`
- `artifact_trace`
- `approval`
- `suggestions`
- `error`
- `done`

约束：

- `metadata` 必须尽早发送，至少包含 `thread_id` 与 `run_id`
- 所有运行态事件应尽量包含 `run_id`
- 涉及用户隔离的运行态逻辑必须在后端保留 `user_id`
- `error` 事件要给出用户可理解信息，同时后台日志保留可排查细节
- `done` 只表示本次 SSE 流结束，不等同于所有后台任务永久成功


### 10.2 统一产物对象契约

- 前端展示以 artifact 对象为准，不从聊天文本中猜测产物
- 修改产物必须保留版本关系
- `ready` 前不应暴露下载 URL
- `failed` 必须能展示失败原因的用户可读摘要
- 后端读取或修改 artifact 时必须校验 `user_id`

### 10.3 统一进度步骤对象契约

所有流程卡片统一抽象为 progress step，至少包含：

```ts
type ProgressStep = {
  step_key: string
  label: string
  status: "pending" | "running" | "success" | "failed"
  detail?: string
  started_at?: string
  finished_at?: string
}
```

要求：

- `step_key` 应能映射到 graph 节点、agent 子任务或明确的后台任务
- 前后端不应各自定义一套完全不同的步骤语义
- 新增步骤时同步更新后端 `progress.py` 和前端展示逻辑

### 10.4 Agent Trace 契约

产物子 Agent 与后续评估 Agent 的执行轨迹应统一抽象为 trace entry：

```ts
type AgentTraceEntry = {
  entry_id: string
  kind: "status" | "tool_call" | "tool_result" | "ai_message" | "error"
  title: string
  content?: string
  status?: "running" | "success" | "failed"
  created_at?: string
}
```

约束：

- trace 内容必须做长度截断
- 不记录完整敏感上下文
- 不记录 JWT、密码、完整附件内容、完整记忆内容
- 工具输入输出只记录摘要或必要字段

## 11. 变更验收清单

### 后端

- API schema 是否同步更新
- 查询和修改是否按 `user_id` 做资源归属过滤
- graph 是否接入新状态或新节点
- Agent 工具权限、审批、错误分类是否明确
- 文件处理链路是否与 `knowledge_files` / `attachment_files` / `artifact_files` 正确对应
- 失败状态是否可追踪、可返回、可展示
- 是否保留 `run_id`、`thread_id`、`plan_id`、`user_id` 的日志关联
- 涉及长链路或 Agent 行为时，是否发出必要 observation 事件，且字段已脱敏、截断并避免高基数 Prometheus label
- 是否新增或更新必要测试
- 涉及 Agent 行为变化时，是否增加评估用例或回归样本

### 前端

- 消息渲染是否兼容旧事件与新事件
- 进度卡片是否来自真实后端事件
- 产物展示是否接入统一 artifact 模型
- 审批卡片是否能正确恢复中断
- 产物 trace 是否做长度与布局保护
- 文件下载、预览、OnlyOffice 配置是否能携带必要 token
- 错误、失败、空状态是否可理解
- 回退兼容是否保留

### Agent、存储与评估

- 是否明确新增能力属于哪个 Agent 或 graph 节点
- 是否明确可用工具与禁止工具
- 是否明确属于哪条文件链路或记忆链路
- 是否有最小可复现用例
- 是否能通过评估集或回归测试证明没有破坏旧能力
- 是否能从日志或 trace 中解释失败原因
- 是否需要更新 `backend/tests/evals/`、`docs/observability/` 或 Grafana/Prometheus/OTel 相关接入说明

## 12. 协作建议

- 开工前先读本文件，再读对应模块入口文件
- 对话、进度、产物、附件、审批、trace、认证、存储、记忆这几类能力优先看成“协议问题”，其次才是 UI 问题
- 需求不明确时，优先追问澄清或做对后续演进最稳的抽象，不做一次性特判
- 新阶段开发时，默认把“Agent 行为是否可控、可测、可观测”放在和“功能是否跑通”同等重要的位置

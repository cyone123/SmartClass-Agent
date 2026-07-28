# SmartClass Demo 企业级落地技术评估报告

评估日期：2026-07-04  
评估对象：`D:\Learn\langchain\demo`  
评估视角：企业级生产落地、可扩展性、可靠性、安全合规、工程交付与 AI Agent 治理

## 1. 结论摘要

SmartClass Demo 已经不是单纯原型：主流程能力、JWT 登录、用户资源隔离、RAG、产物生成、对象存储抽象、LangGraph 长期记忆、SSE 事件、评估 harness、Prometheus/OTel/Grafana 接入雏形都已经具备。这说明项目已经完成了“业务闭环”和“Agent 治理雏形”。

但距离真正可落地的企业级项目，仍存在明显差距。核心差距不在“功能是否能演示”，而在以下方面：

- 数据库治理仍偏 demo：自动 `create_all` 建表，缺少迁移体系、约束体系、复合索引、软删除/审计/租户模型和容量治理。
- 高并发与高可用能力不足：文件入库使用单进程内存队列，Agent 执行与 SSE 长连接强耦合，缺少分布式任务队列、限流、背压、超时预算、水平扩展一致性设计。
- 安全边界需要收紧：默认 admin、默认 JWT secret、全开放 CORS、OnlyOffice JWT 关闭、token query 传播、本地 workspace 执行模式等都不适合直接生产暴露。
- 工程化门禁不足：未看到 CI/CD、Alembic、lint/type check、前端测试、依赖锁定策略、镜像安全扫描、发布回滚与环境分层配置。
- 可观测性已有基础，但还没有形成 SLO、告警、运行摘要、任务级追踪和故障归因闭环。
- AI Agent 已有 harness 和评估体系，但企业级还需要更强的策略治理、成本治理、审计、红队测试、回归门禁和模型供应商降级方案。

综合判断：当前项目适合继续作为“高保真工程 demo / 内部试点 MVP”。若要进入企业级生产，需要先完成“数据迁移与任务队列化、安全基线、部署高可用、工程门禁”四条主线。

## 2. 成熟度评分

| 维度 | 当前评分 | 企业级目标 | 主要差距 |
| --- | ---: | ---: | --- |
| 业务闭环 | 7/10 | 8/10 | 主流程完整，但异常、回滚、补偿和批量运营能力不足 |
| 数据库设计 | 4/10 | 8/10 | 无迁移体系，约束和索引不足，审计字段不完整 |
| 高并发能力 | 3/10 | 8/10 | 单进程队列、长连接 Agent 流式执行、缺少限流和背压 |
| 高性能设计 | 4/10 | 8/10 | 上传/下载全量读内存，RAG 参数固定，缺少缓存和性能基线 |
| 高可用设计 | 3/10 | 8/10 | Compose 单机部署，缺少多副本、任务幂等、故障转移、备份恢复 |
| 安全合规 | 4/10 | 9/10 | 默认密钥/账号、CORS 全开、OnlyOffice JWT 关闭、token query 风险 |
| 可观测性 | 6/10 | 8/10 | 基础设施已具备，但缺 SLO、告警和关键业务运行摘要 |
| 测试与评估 | 6/10 | 8/10 | 后端和 eval 较好，缺 CI、前端测试、集成压测、安全测试 |
| DevOps 工程化 | 4/10 | 8/10 | 有 Docker，但缺发布流水线、镜像治理、环境分层和 IaC |
| AI Agent 治理 | 6/10 | 9/10 | 有工具策略和评估雏形，缺企业级审计、成本、红队和回归门禁 |

## 3. 当前架构概览

```text
浏览器/Vue
  |
  | REST + SSE
  v
FastAPI Backend
  |
  +-- Auth / Plan / Session / File / Memory API
  +-- LangGraph Agent Runtime
  +-- Workspace Code Execution
  +-- File Ingestion Runtime, single-process asyncio.Queue
  |
  +-- PostgreSQL: 业务表 + LangGraph checkpoint/store + PGVector
  +-- MinIO 或 Local Storage
  +-- Prometheus / OTel / Grafana demo stack
```

当前架构优点：

- 前后端主链路清晰，资源通过 `user_id` 归属过滤。
- 文件链路开始统一到 `StorageService`，已经为 MinIO 兼容对象存储打基础。
- Agent 主流程有 LangGraph checkpoint/store、长期记忆、approval interrupt 和 SSE 事件。
- 可观测性模块已经有结构化日志、Prometheus、OpenTelemetry 和 Grafana dashboard 雏形。
- 后端已有不少单测和 Agent eval cases，说明团队已经意识到 Agent 行为不可只靠人工验收。

当前架构短板：

- Web 请求、Agent 执行、文件入库和产物生成仍在一个后端服务进程内耦合过重。
- 后台任务、模型调用、文件处理、对象存储、OnlyOffice 回调都缺少统一任务状态和补偿机制。
- 生产部署仍以 Docker Compose 单机为主，不是面向多节点、多副本、滚动发布和容灾恢复的架构。

## 4. 数据库设计问题与提升方向

### 4.1 缺少数据库迁移体系

代码证据：

- `backend/app/dependencies/db.py` 中 `init_db()` 使用 `Base.metadata.create_all` 自动建表。
- 仓库未发现 Alembic 或 migration 目录。

风险：

- 无法可靠管理生产数据库 schema 演进。
- 无法评审每次 DDL 变更、回滚变更或做灰度发布。
- 自动建表不能处理字段修改、索引调整、约束变更、数据回填。

建议：

- 引入 Alembic。
- 禁止生产启动时自动 `create_all`。
- 每次 schema 变更必须有 migration、回滚策略和数据迁移说明。
- CI 中增加 migration 校验：空数据库可迁移成功，历史数据库可升级成功。

### 4.2 约束和索引不够企业级

现状：

- 多数表有单列 `index=True`，例如 `user_id`、`plan_id`、`thread_id`、`status`。
- 业务查询经常按组合条件过滤，例如 `user_id + plan_id + status`、`user_id + thread_id + artifact_type + is_current`。
- `ArtifactFile.is_current` 由应用层维护，没有唯一约束保护同一 artifact 类型只能有一个当前版本。
- `Session.thread_id` 没有看到唯一约束。

风险：

- 并发修改产物时可能出现多个 current artifact。
- 用户、计划、线程维度查询在数据量上来后退化。
- 缺少数据库约束会把一致性压力全部压到应用代码。

建议：

- 为主要查询建立复合索引：
  - `knowledge_files(user_id, plan_id, status, id)`
  - `attachment_files(user_id, plan_id, thread_id, id)`
  - `artifact_files(user_id, thread_id, artifact_type, is_current, updated_at)`
  - `teaching_sessions(user_id, thread_id)`
- 增加关键唯一约束或部分唯一索引：
  - `users(username)` 已有唯一约束，可保留。
  - `teaching_sessions.thread_id` 建议全局唯一，或至少 `(user_id, thread_id)` 唯一。
  - `artifact_files` 对 ready/current 版本建立部分唯一约束，避免并发写出多个 current。
- 为外键约束明确 `ondelete` 行为，避免用户、计划删除后残留大量孤儿数据。

### 4.3 缺少完整审计与软删除模型

现状：

- 文件和产物有 `created_at/updated_at`，但 `Plan` 和 `Session` 模型没有看到创建/更新时间。
- `KnowledgeFile` 有 `deleted` 状态，其他资源没有统一软删除。
- 长期记忆、Agent 工具调用、OnlyOffice 回写等高风险操作没有统一审计表。

风险：

- 难以回答企业客户常问的问题：谁在什么时候上传、下载、修改、删除了什么。
- 出现越权、误删、产物错误时缺少业务审计链。
- 不利于合规、数据保留、客户支持和问题复盘。

建议：

- 统一所有业务表的审计字段：`created_at`、`updated_at`、`deleted_at`、`created_by`、`updated_by`。
- 增加 `audit_events` 表，记录登录、文件下载、OnlyOffice 回写、产物生成/修改、记忆创建/删除、管理员操作。
- 审计内容只保存摘要和引用 ID，不保存完整 prompt、附件正文、JWT、对象 key。

### 4.4 多租户模型不足

现状：

- 当前以 `user_id` 做私有资源隔离。
- `role`、`is_superuser` 已存在，但没有完整组织、学校、班级、RBAC、共享资源模型。

风险：

- 企业客户通常需要组织级管理、教师协作、学校数据隔离、知识库共享和管理员审计。
- 后期再补租户字段成本较高，尤其是 RAG、对象存储 key、LangGraph store namespace 已经产生历史数据后。

建议：

- 增加 `tenant_id` 或 `organization_id`，明确租户边界。
- 所有用户私有或租户私有资源都纳入 `tenant_id + user_id` 双层过滤。
- RAG metadata、对象存储 key、LangGraph memory namespace 同步引入租户维度。
- 将 `role/is_superuser` 演进为可配置 RBAC 或 ABAC 策略。

## 5. 高并发与高性能问题

### 5.1 文件入库是单进程内存队列

代码证据：

- `backend/app/core/file_ingestion.py` 使用 `asyncio.Queue[int]`。
- 只有一个 `_worker_task` 消费。
- 失败时只 `print`，没有任务表、重试次数、死信队列或分布式锁。

风险：

- 多副本部署时每个副本都有自己的内存队列，任务不可见、不可协调。
- 进程重启会丢失队列中的未持久化任务。
- 大量文件上传时无法横向扩容 ingestion worker。
- 单个慢文件会阻塞后续文件。

建议：

- 引入持久化任务队列：Celery/RQ/Arq + Redis，或数据库任务表 + worker。
- 任务字段至少包括：`task_id`、`task_type`、`resource_id`、`status`、`attempts`、`next_retry_at`、`locked_by`、`locked_until`、`error_category`。
- 支持并发 worker、指数退避、幂等处理、死信队列和人工重试。
- 将文件入库、视频分析、产物生成、OnlyOffice 回写后重索引都纳入统一任务系统。

### 5.2 SSE 长连接与 Agent 执行耦合

现状：

- `/api/chat/stream` 在请求生命周期内直接驱动 `agent_runtime.stream_agent_events`。
- Agent token、progress、artifact、approval 都通过当前 SSE 连接推送。

风险：

- 长连接占用服务端连接和 worker 时间。
- 用户断开连接后，长任务如何继续、取消、恢复并不清晰。
- 产物生成和模型调用很慢时，容易造成请求堆积。
- 多副本部署时前端重连需要路由到可恢复状态，而不仅是某个进程内状态。

建议：

- 将“请求入口”和“Agent 运行”拆开：
  - 请求创建 `run_id` 和任务记录。
  - Agent worker 异步执行。
  - SSE 只订阅 `run_id/thread_id` 的事件流。
- 使用 Redis Stream、PostgreSQL outbox、Kafka/NATS 等事件通道承载运行态事件。
- SSE 支持 `Last-Event-ID` 和事件补拉，避免网络中断丢事件。
- 为每次 run 建立超时预算和取消机制。

### 5.3 上传和下载存在全量内存读写

代码证据：

- `file_service._read_and_validate_upload_file()` 使用 `await upload_file.read()` 一次性读取整个上传内容。
- 下载接口使用 `get_storage_service().read_bytes()` 后一次性 `Response(content=data)` 返回。
- OnlyOffice 回调下载 `_download_onlyoffice_document_bytes()` 将所有 chunks 拼成 bytes。

风险：

- 文件大小限制目前默认 20MB，短期可接受，但企业环境很容易要求更大课件、视频、PDF。
- 并发上传/下载时内存占用成倍增长。
- 大文件经过应用代理下载会拖慢后端。

建议：

- 上传改为流式写入临时文件或对象存储 multipart upload，同时流式计算 sha256。
- 下载优先使用对象存储预签名 URL 或 StreamingResponse。
- OnlyOffice 回写直接流式写对象存储，避免 `b"".join(chunks)`。
- 设置 Nginx/网关层上传限制、后端超时、对象存储 multipart 策略。

### 5.4 RAG 参数和向量维度硬编码

代码证据：

- `backend/app/core/rag.py` 中 `self.vector_size = 3072`。
- chunk 参数固定为 `chunk_size=250`、`chunk_overlap=20`。

风险：

- 切换 embedding 模型时，向量维度可能不匹配。
- 不同文档类型、学科、语言下固定 chunk 策略效果不稳定。
- 缺少索引版本，历史向量与新模型向量无法清晰共存。

建议：

- 将 embedding 模型、维度、chunk 策略、retrieval `k` 配置化。
- 增加 `embedding_model_version`、`index_version`、`chunk_strategy` metadata。
- 支持索引重建任务和双索引灰度。
- RAG eval 增加召回率、引用准确率、无关召回抑制等指标。

### 5.5 缺少缓存与成本控制

现状：

- LLM、embedding、文件解析、附件分析、产物生成均可能重复调用。
- 配置中有 prompt cache 开关，但缺少企业级统一缓存与成本预算视图。

建议：

- 引入按用户/租户/run 的 token usage、费用估算和预算限制。
- 对确定性强的步骤做缓存：文件解析结果、embedding、附件摘要、结构化抽取。
- 建立模型调用限流：按用户、租户、IP、接口和模型类型分别限制。
- 对高成本任务增加排队、确认和取消能力。

## 6. 高可用与灾备问题

### 6.1 部署仍是单机 Compose 形态

现状：

- `docker-compose.yml` 覆盖 backend、frontend、postgres、minio、onlyoffice、otel、prometheus、grafana。
- 没有 Kubernetes/Helm、滚动发布、HPA、PodDisruptionBudget、资源限制和多副本配置。

风险：

- 任一核心容器故障都会造成服务不可用或能力降级。
- 数据库、MinIO、OnlyOffice 仍是单点。
- 不能支撑企业客户要求的 SLA。

建议：

- 生产形态拆为：
  - stateless API 服务，多副本。
  - Agent/worker 服务，独立扩缩容。
  - PostgreSQL 托管高可用或主从架构。
  - 对象存储使用云 S3/OSS/COS 或 MinIO 分布式集群。
  - OnlyOffice 独立部署并启用 JWT。
- 提供 Kubernetes manifests 或 Helm chart。
- 为所有服务设置 CPU/memory request/limit、readiness/liveness probe、滚动升级策略。

### 6.2 健康检查过浅

代码证据：

- `/health` 仅返回 `{"status": "healthy"}`。

风险：

- 数据库断开、MinIO 不可用、RAG 未初始化、LangGraph checkpointer 异常时，健康检查仍可能成功。
- 负载均衡器无法把异常实例摘除。

建议：

- 拆分：
  - `/health/live`：进程存活。
  - `/health/ready`：数据库、存储、RAG、模型配置、队列连接可用。
  - `/health/dependency`：用于运维排查，可带依赖详情但需鉴权或内网访问。
- readiness 失败时停止接收流量，但不一定重启进程。

### 6.3 缺少备份恢复和数据生命周期

风险范围：

- PostgreSQL 业务数据、LangGraph checkpoint/store、PGVector 向量表。
- MinIO 对象：知识库、附件、产物、workspace 输出。
- Grafana dashboard、Prometheus 指标、JSONL trace。

建议：

- 制定 RPO/RTO。
- PostgreSQL 启用定期全量备份 + WAL 归档 + 恢复演练。
- MinIO/S3 启用版本控制、生命周期策略和跨区域复制。
- 文件删除采用延迟物理删除，避免误删不可恢复。
- 将灾备演练纳入季度检查。

## 7. 安全与合规问题

### 7.1 默认密钥和默认账号不适合生产

代码证据：

- `auth.py` 默认 JWT secret 为 `smartclass-dev-secret`。
- `auth_service.py` 自动创建 `admin/admin12345`。
- `.env.docker.example` 中仍有多处示例弱密码。

风险：

- 生产误用默认配置会导致系统完全失守。
- 默认 admin 账号会成为扫描器和攻击者首要目标。

建议：

- 生产启动时如果 `JWT_SECRET_KEY` 为默认值或过短，直接失败。
- 默认 admin 只能在开发环境创建，生产必须通过初始化命令或后台管理流程创建。
- 密钥统一从 Secret Manager 或 Kubernetes Secret 注入。
- 增加密码策略、登录失败锁定、验证码或 MFA。

### 7.2 CORS 全开放

代码证据：

- `main.py` 中 `allow_origins=["*"]` 且 `allow_credentials=True`。

风险：

- 浏览器环境下跨站调用边界过宽。
- 与本地存储 token 组合时，XSS 后果严重。

建议：

- 按环境配置允许的前端域名。
- 生产禁用 `*`。
- 增加安全响应头：CSP、X-Frame-Options/Frame-Ancestors、Referrer-Policy、X-Content-Type-Options。

### 7.3 token query 参数传播风险

现状：

- 下载、预览、OnlyOffice 配置/回调支持 `access_token` query 参数。
- 前端 token 存在 localStorage。

风险：

- query token 可能进入浏览器历史、代理日志、Referer、OnlyOffice 日志。
- localStorage token 易受 XSS 影响。

建议：

- 对浏览器用户会话优先使用 HttpOnly + Secure + SameSite cookie。
- 对 OnlyOffice 等第三方回调使用短期一次性 document token，不复用用户 JWT。
- query token 使用极短 TTL、单用途、可撤销，并避免进入通用 access token。
- 下载链接使用后端签发的短期 download token，绑定用户、文件、操作类型和过期时间。

### 7.4 OnlyOffice JWT 关闭

代码证据：

- `docker-compose.yml` 中 `onlyoffice` 服务配置 `JWT_ENABLED: "false"`。

风险：

- OnlyOffice 与后端之间缺少文档服务级别的请求签名。
- 回调来源验证不足，存在伪造回调风险。

建议：

- 生产启用 OnlyOffice JWT。
- 回调增加签名验证、来源 allowlist、文件大小限制、内容类型校验和下载 URL 域名 allowlist。
- 对回写操作写审计事件。

### 7.5 Workspace 执行仍需生产隔离

现状：

- 支持 `local` 和 `daytona` 两种执行后端。
- local 后端会在主机/容器内直接执行 Python/Node 文件，虽有路径和安装命令限制。

风险：

- Agent 生成代码在业务容器内执行，生产风险较高。
- 安装命令正则无法覆盖所有逃逸方式。
- 缺少 seccomp/AppArmor、网络隔离、文件系统只读、CPU/memory 限额等强隔离。

建议：

- 生产禁用 local workspace execution。
- 强制使用独立沙箱：Daytona、Firecracker、gVisor、Kubernetes Job sandbox。
- 每次 run 单独资源配额、网络默认拒绝、输出目录白名单、执行审计。
- 对产物生成脚本进行静态扫描和动态超时控制。

## 8. 工程化与交付问题

### 8.1 缺少 CI/CD 与质量门禁

现状：

- 未发现 `.github/workflows`。
- 后端有测试，前端未看到测试脚本。
- 没有统一 lint/type check 配置，如 `pyproject.toml`、ruff、mypy、prettier/eslint。

建议门禁：

- Python：ruff、black、mypy 或 pyright、pytest、coverage。
- Frontend：eslint、prettier、vitest、playwright e2e。
- Docker：镜像构建、Trivy/Grype 漏洞扫描、SBOM。
- DB：Alembic migration 校验。
- Agent：eval regression gate，关键指标低于阈值禁止合并。

### 8.2 依赖版本策略不稳定

现状：

- `requirements.txt` 大量使用 `>=`，缺少 lock 文件。
- 前端 `package.json` 使用 caret 版本，虽然有 lock 文件但需要纳入 CI。

风险：

- 构建不可复现。
- LangChain/LangGraph/OpenTelemetry 等生态变化快，兼容性风险高。

建议：

- 使用 `pip-tools`、Poetry 或 uv 生成锁定版本。
- 将后端依赖分为 runtime、dev、test。
- 建立依赖升级节奏和回归测试。
- 对模型 SDK、LangGraph、langchain-postgres 等核心依赖单独做兼容性测试。

### 8.3 Git 与仓库卫生问题

观察：

- 当前根工作区有修改和未跟踪文件。
- 前后端子目录触发 Git dubious ownership。
- 代码树中可见 `__pycache__`、`.pytest_cache`、eval results 等本地生成文件。

风险：

- 协作时很容易把本地生成物、环境差异或历史变更混入提交。
- 子模块/嵌套仓库边界不清晰会影响 CI、发布和代码审查。

建议：

- 明确 monorepo 或 submodule 策略。
- 完善 `.gitignore`，清理已入库的缓存和本地结果文件。
- 新增 `make verify` 或 `scripts/verify.ps1`，统一本地检查。
- 建立分支保护和 PR 模板。

## 9. 可观测性与运维问题

### 9.1 已有基础

当前较好的部分：

- `RunContext` 串联 `run_id/thread_id/plan_id/user_id/agent_name`。
- Prometheus endpoint 可选开启。
- OTel Collector 和 Grafana dashboard 有本地配置。
- 测试中覆盖了 Prometheus 低基数标签等关键约束。

### 9.2 缺少 SLO 和告警

现状：

- Grafana dashboard 主要展示请求速率、失败事件、LLM calls、文件/产物/存储/workspace。
- Prometheus 配置只有 scrape，没有 alert rules。
- OTel Collector 默认 debug exporter，没有生产后端落点。

建议：

- 定义 SLO：
  - API 可用性。
  - chat 首 token 延迟。
  - 产物生成成功率和 P95 时延。
  - 文件入库成功率和 P95 时延。
  - LLM 错误率、超时率、限流率。
- 建立告警：
  - SSE error rate 超阈值。
  - 文件入库积压。
  - artifact failed rate 升高。
  - DB pool exhausted。
  - MinIO/对象存储失败。
  - LLM provider 错误或成本异常。
- 每次 Agent run 结束写运行摘要：输入摘要、节点路径、工具调用摘要、token usage、产物结果、失败分类。

## 10. AI Agent 治理与评估问题

### 10.1 现有优势

- LangGraph 流程已经包含意图识别、记忆加载、信息追问、审批中断、产物路由、记忆反思。
- `backend/tests/evals/` 已有 intent、memory、extraction、context compression 评估用例。
- workspace 工具有路径校验、输出截断、安装命令拦截和部分工具策略 middleware。

### 10.2 企业级还缺什么

问题：

- Agent 行为回归还没有接入 CI 质量门禁。
- 工具调用审计还没有形成独立查询界面或审计表。
- 缺少安全红队 eval：越权文件访问、提示注入、RAG 污染、恶意附件、产物 HTML 安全。
- 模型供应商降级、超时、限流、预算和 fallback 策略还不够体系化。
- 记忆写入需要更强的用户可见解释和隐私最小化审计。

建议：

- 将 eval 分层：
  - 单节点 eval：intent、extraction、memory、RAG。
  - 端到端 eval：教学计划到产物生成。
  - 安全 eval：越权、泄漏、工具滥用、prompt injection。
  - 性能 eval：首 token、总时长、token 成本。
- 每次模型、prompt、工具策略变更必须跑相关 eval。
- 建立 Agent policy registry：每类 Agent 可用工具、禁止工具、审批要求、输出 schema、错误分类。
- 所有工具调用写入审计事件，字段只含摘要和安全 metadata。

## 11. 前端工程与用户体验风险

现状：

- 前端 Vue + Pinia + Element Plus 已能消费 SSE 和 artifact 事件。
- Axios 自动带 Bearer token，401 清理登录态。
- token 存 localStorage。

问题：

- 缺少前端单测、组件测试、E2E 测试。
- SSE 重连、断线恢复、事件补偿能力不明显。
- 长任务的取消、重试、后台继续执行、历史事件追踪仍偏弱。
- 安全上 localStorage token 和 HTML artifact preview 需要更严 CSP/沙箱策略。

建议：

- 增加 Playwright 端到端场景：登录、上传知识库、聊天 SSE、产物生成、OnlyOffice 预览、HTML 预览。
- SSE 客户端实现重连和 `run_id` 事件恢复。
- 将 token 迁移到 HttpOnly cookie 或使用短期 session token + refresh token。
- 对 artifact trace、错误、失败状态建立统一 UX 规范。

## 12. 生产落地优先级路线图

### P0：生产安全基线和数据治理

建议周期：1 到 2 周

- 引入 Alembic，停止生产 `create_all`。
- 生产启动校验 JWT secret、默认 admin、CORS、OnlyOffice JWT。
- 收紧 CORS 和安全响应头。
- 禁用生产 local workspace execution。
- 建立关键复合索引和唯一约束。
- 下载/预览 token 改为短期单用途 token。

### P1：任务队列化和水平扩展

建议周期：2 到 4 周

- 引入持久化任务系统，替换单进程 `asyncio.Queue`。
- 文件入库、视频分析、产物生成、OnlyOffice 重索引都进入任务系统。
- Agent run 与 SSE 解耦，事件持久化并支持补拉。
- 建立 worker 多副本、幂等、重试、死信和取消机制。

### P2：可观测性、SLO 和工程门禁

建议周期：2 到 3 周

- 增加 CI：后端测试、前端 build/test、lint、类型检查、Docker build、依赖扫描。
- eval regression 进入 PR 门禁。
- Prometheus alert rules、Grafana dashboard、OTel 生产后端接入。
- 增加运行摘要、任务积压、DB pool、对象存储、LLM provider 监控。

### P3：多租户、权限和企业管理能力

建议周期：4 到 8 周

- 引入 tenant/organization/school 模型。
- 建立 RBAC/ABAC、管理员审计、用户生命周期管理。
- 支持组织级知识库、共享产物和协作权限。
- 数据保留、导出、删除、审计报表。

### P4：AI Agent 企业治理

建议周期：持续演进

- Agent policy registry。
- 安全红队 eval。
- RAG 评估、产物质量评估、成本评估。
- 多模型 fallback、预算控制、降级策略。
- 记忆隐私最小化和用户可解释管理。

## 13. 推荐目标架构

```text
                 ┌────────────────────┐
                 │  Web / Mobile / SSO │
                 └─────────┬──────────┘
                           │
                   API Gateway / WAF
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
┌───────▼────────┐                    ┌───────▼────────┐
│ FastAPI API     │                    │ SSE/Event API   │
│ stateless pods  │                    │ subscribes runs │
└───────┬────────┘                    └───────┬────────┘
        │                                     │
        │ create run/task                     │ read events
        ▼                                     ▼
┌────────────────┐      publish       ┌────────────────┐
│ Task Queue      │──────────────────▶│ Event Stream    │
│ Redis/RabbitMQ  │                   │ Redis/NATS/Kafka│
└───────┬────────┘                   └────────────────┘
        │
┌───────▼──────────────────────────────────────────────┐
│ Worker Pools                                          │
│ - Agent worker                                        │
│ - File ingestion worker                               │
│ - Artifact generation worker                          │
│ - Video/Office worker                                 │
└───────┬──────────────────────────────────────────────┘
        │
        ├── PostgreSQL HA: business + checkpoint + memory + vector
        ├── Object Storage: S3/OSS/MinIO distributed
        ├── Sandbox Execution: Daytona/K8s Job/gVisor
        ├── Model Providers: primary + fallback + budget control
        └── Observability: Prometheus + OTel + logs + audit events
```

## 14. 验收指标建议

企业级改造不应只看“功能完成”，建议按以下指标验收：

| 类型 | 指标 |
| --- | --- |
| 可用性 | API 月可用性、SSE 成功完成率、任务最终成功率 |
| 性能 | chat 首 token P95、产物生成 P95、文件入库 P95、下载吞吐 |
| 稳定性 | 任务重试成功率、死信数量、DB pool 等待时间、worker 队列积压 |
| 安全 | 默认密钥阻断、越权测试通过率、OnlyOffice 回调签名覆盖率、审计完整率 |
| 数据 | migration 成功率、备份恢复演练 RTO/RPO、对象存储丢失率 |
| AI 质量 | intent/extraction/RAG/artifact/security eval pass rate |
| 成本 | 每 run 平均 token、每 artifact 平均成本、模型失败 fallback 成功率 |

## 15. 总体建议

SmartClass Demo 的方向是对的：不是只做聊天，而是把教学计划、知识库、产物、审批、记忆和评估逐步纳入统一协议。这是 Agent 产品企业化的正确起点。

下一步不要优先继续堆更多产物类型或 UI 功能。更高价值的路线是先把“生产地基”补齐：

1. 数据库迁移、索引、约束、审计。
2. 后台任务队列化和 Agent/SSE 解耦。
3. 安全基线收紧，尤其是默认账号、CORS、OnlyOffice、token 传播和 workspace 执行。
4. CI/CD、eval 门禁、可观测性告警。
5. 多租户和企业权限模型。

完成这些后，项目才会从“能演示、能试点”逐步进入“能稳定交付、能被企业运维、能承受真实用户和数据规模”的阶段。

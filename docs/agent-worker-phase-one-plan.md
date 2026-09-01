# 第一批改造方案：独立 Agent Worker 与 Redis 任务分发

状态：待实现的设计方案。本文不代表已有功能。

## 1. 目标与范围

采用 PostgreSQL + Redis Streams + 独立 Python asyncio Worker。

第一批完成：

- API 进程重启、浏览器断网或切换会话时，独立 Worker 中已经启动的 Agent 继续执行。
- 创建 Run 和待投递记录事务一致；队列消息重复或丢失时，可依据数据库恢复调度。
- 同一 thread 只有一轮获得执行权；不同 thread 可以分配给不同 Worker。
- 支持跨进程取消、执行租约、失联检测和明确的失败收尾。
- 保持原有 PostgreSQL 事件、文本快照、SSE 序号回放和审批语义。

第一批不自动重跑已经进入 running 的 Run，不恢复被中断的模型网络流，不承诺产物副作用 exactly-once。Worker 崩溃后的 checkpoint 恢复与产物执行幂等属于第二批。Redis 本批只分发执行命令，不存 token，也不接管 SSE。

部署范围先限定为同一 Compose 主机，默认一个 Worker、并发一轮。通过两个 Worker 的并发领取测试验证隔离；多主机共享存储、整个应用的多 API 副本能力另行验证，不能把本批的聊天执行隔离推广为全应用已支持水平扩容。

## 2. 进程职责

```text
浏览器 POST /chat/runs
        ↓
API：鉴权、校验、同事务创建 Run + Outbox
        ↓
PostgreSQL ← 调度器读取与对账
        ↓
调度器 → Redis chat:jobs → Agent Worker
                              ↓
                        AgentRuntime / LangGraph
                              ↓
                  PostgreSQL 事件、快照、checkpoint
                              ↓
                  API 的现有 SSE → 浏览器
```

- API：提交、查询、SSE、取消请求；redis 模式下不启动 ChatRunManager 执行任务，也不扫描所有 active Run 并标失败。
- 调度器：Outbox 投递、queued Run 对账、失联 Run 收尾、已结束消息清理。独立进程，支持通过数据库领取锁避免多个实例重复处理。
- Worker：消费任务、原子领取执行权、初始化 Agent 依赖、执行、续租、处理取消、持久化终态、ACK。
- PostgreSQL：业务与执行状态的最终依据。
- Redis：可重复交付的调度通道；不能作为判断 Run 是否执行完成的唯一依据。

API 暂时保留现有 AgentRuntime 初始化，因为历史查询、审批校验和记忆 API 仍依赖它。抽取共享初始化函数给 Worker 使用；Worker 不启动 FastAPI，也不启动 FileIngestionRuntime。文件入库继续沿用原链路，避免顺带改变其他后台任务。

## 3. 数据模型与迁移

### agent_runs 新增字段

| 字段 | 用途 |
| --- | --- |
| execution_backend | in_process / redis，创建后不随全局配置改变 |
| worker_id | 本次 Worker 进程启动生成的身份 |
| execution_token | 每次成功领取生成的 UUID，用于条件写入 |
| heartbeat_at | 最近一次续租时间，使用数据库时钟 |
| lease_expires_at | 执行权到期时间 |
| cancel_requested_at | 持久化取消请求 |
| error_code | worker_lost、shutdown_interrupted 等稳定错误码 |
| execution_guard_held | 是否仍占用该 thread 的执行资格 |

为 thread_id 创建 execution_guard_held=true 的部分唯一索引。创建 Run 即占用资格；正常结束或确认停止后释放。进程状态不明时保留资格，即使 Run 对外已标失败，也不允许同 thread 马上启动下一轮。

现有会话行锁继续用于提交与归属校验。创建、领取、取消、结束使用短事务，不在模型调用期间持有普通行事务。Worker 执行前再次校验 thread、附件归属和审批 interrupt；队列等待可能使提交时的校验结果过期。

### 新增 chat_run_outbox

字段：id、run_id、dispatch_version、schema_version、status、attempts、next_attempt_at、claim_token、claim_expires_at、published_at、redis_message_id、created_at。

- (run_id, dispatch_version) 唯一；同一 Run 同时最多一个未结束投递记录。
- status 为 pending / publishing / published / obsolete；claim 字段处理投递器中途退出。
- 队列 payload 只含 schema_version、outbox_id、run_id、dispatch_version。
- attempts 是投递尝试次数，不是模型执行次数。
- Run 结束后未投递的记录标 obsolete。

### 迁移办法

当前 init_db() 使用 Base.metadata.create_all()，已有表需要显式 ALTER 和索引迁移。增加一个带版本记录、事务和迁移锁的数据库升级入口，作为单独的部署步骤执行；不让每个 API/Worker 启动时竞争修改表。

新旧数据库都测试升级：旧记录回填 execution_backend=in_process，终态记录 guard=false。切换前排空旧 active Run；不能在旧进程仍执行时直接将它们标失败。添加唯一索引前检查重复占用并失败退出，不能静默删除数据。

## 4. 提交与投递协议

1. API 校验用户、thread、附件和审批。
2. 在一个事务中创建 queued Run、占用 thread 执行资格、创建 pending Outbox。
3. 提交成功返回现有 202 快照。Redis 暂时不可用时仍可接受进入 queued；通过可配置队列容量门限控制积压，达到门限在提交前返回 503。
4. 调度器用 FOR UPDATE SKIP LOCKED 领取到期 Outbox，写 claim_token/过期时间后提交短事务。
5. 在事务外调用 XADD；成功后按 claim_token 条件标 published。网络失败按带抖动退避重新投递。
6. XADD 成功但标记失败会产生重复消息，由 Worker 的数据库领取逻辑去重。

另设 queued 对账循环：对长期未领取且没有有效投递 claim 的 Run，条件创建新 dispatch_version。即使 Redis 故障丢失已发布消息，也可以重新调度。领取时检查版本；旧版本消息作为过期通知清理。对账仅覆盖 queued，不能将 running 重新排队。

调度器 Redis 失败时继续执行 PostgreSQL 中的取消/租约检查；这些职责不能被一次阻塞的网络调用拖住。

## 5. Worker 执行协议

任务 Stream：chat:jobs；Consumer Group：agent-workers。名字来自配置并带部署环境前缀。新建 group 使用 0-0 和 MKSTREAM，确保 group 建立前的消息可消费。

Worker 先获得本地并发额度，再 XREADGROUP 领取，避免在进程内预取大量未运行的 Run。

数据库领取逻辑：

```text
不存在 / 已终态 / 投递版本过期 → 清理对应消息，不执行
queued 且已请求取消            → 原子 cancelled + done，不执行
queued 且有效                  → 原子 running + token + lease，执行一次
running 且租约有效             → 不执行，保持有效消息等待原执行者收尾
running 且租约过期             → 进入失联处理，不重新执行
```

执行前先提交 running。这意味着领取成功但还没进入模型就崩溃，也按可能已执行处理；第一批选择保守失败，不猜测执行到了哪里。

抽取现有 _execute_run 的主体为 ChatRunExecutor，沿用 metadata、progress、token、artifact、artifact_trace、approval、suggestions、error。所有 Run 事件与终态写入检查 status=running、execution_token 匹配及租约有效。

正常完成时，一次事务完成 final status、completed_at、done 和 guard 释放。看到 approval 时结束为 waiting_approval；再次审批创建新 Run，不长时间占住 Worker。

只有数据库终态已提交后才 ACK 当前消息；ACK 丢失引发重投时，终态检查避免重复执行。XACK 只删除 Pending 记录，不删除 Stream 内容；单 consumer group 前提下，成功 ACK 后清理已结束对应消息，后台清理终态副本。不能用盲目 MAXLEN 裁剪未完成任务。

## 6. 租约、取消与失联

初始参数均可配置：心跳 10 秒、租约 60 秒、取消检查 1 秒、对账扫描 10 秒、优雅停机等待 60 秒。参数是起点，使用慢数据库和事件循环阻塞测试校准。

### 续租

心跳独立于 token 产生。续租是带 token、状态和未过期条件的 UPDATE，并读取取消标记。数据库时间决定租约；请求超时和本地单调时钟用于决定提前停止。租约到期后旧 Worker 不能自行重新续租。

续租失败必须在本地安全截止时间前请求取消 Agent；监督逻辑确认任务停止。单靠事件写入 token 校验不能阻止旧 Agent 写 checkpoint 或外部产物，因此不能宣称租约本身已经实现所有副作用隔离。

### 用户取消

- queued：锁行，直接写 cancelled + done、释放 guard、作废 Outbox。
- running：持久化 cancel_requested_at，返回快照；Worker 检查后取消本地 task，等待清理完成，再写 cancelled + done 并 ACK。
- terminal：幂等返回当前快照。
- 完成与取消竞争：锁行决定顺序；终态已提交时取消不再改写；取消已被记录且执行尚未完成时按取消收尾。
- 无法确认执行停止时，不提前释放 thread guard，也不伪装为已安全取消。

接口保持路径不变，新增快照字段 cancellation_requested 和 execution_blocked。取消请求返回时可能仍为 running，前端显示“正在停止”，收到终态后结束。

### 失联处理

调度器只处理 execution_backend=redis 且租约已过期的 running Run，锁行后再次核对 token 和期限。写 failed、error_code=worker_lost、error 与 done，撤销旧 token，但保留 thread guard。

不自动重新调用 Agent。确认原进程已退出或完成停止后，通过受控的恢复管理命令释放 guard。仅心跳消失不算进程死亡证据。第一批提供列出未释放 guard、说明原因和显式释放的维护入口；自动化进程隔离与安全恢复后续完善。

新消息遇到未释放 guard 返回 409 + EXECUTION_UNCERTAIN；前端显示执行清理未完成，不能将这个冲突当成可继续订阅的 active Run。

未确认任务的 Redis Pending 可通过 XAUTOCLAIM 交给清理者检查，但转移 Pending 所有权不授予 Agent 执行权。健康 running 即使消息 idle 很久也不得重新执行。

产物或 checkpoint 已提交的副作用不回滚；遗留生成状态的产物记录先诊断，确认执行者停止后再修正状态，不擅自删除文件。这不是完整产物幂等方案。

## 7. API、前端和旧链路

- POST /chat/runs、GET /chat/runs/{id}、active、events 保持基本契约。
- SSE 继续从 agent_run_events 回放；本批不修改整数 sequence，也不增加 SSE 事件类型。
- 前端补充 queued、取消处理中、执行清理未完成的提示；正常 409 仍订阅现有 active Run，异常 guard 冲突单独处理。
- 历史先读、随后发现 Run 已结束的竞态：没有 active Run 时补一次受请求身份保护的历史/产物刷新；已知 run_id 时查询终态，避免 API 重启期间漏掉最终回复。
- in_process 模式保留旧 /chat/stream；redis 模式拒绝旧接口直接执行并返回明确升级提示。第一批不再实现第二套旧 SSE 协议适配器。现有 Vue 已走新接口。
- 会话/计划删除检查执行 guard，有占用时返回冲突；防止 Worker 在实体已删除后继续写入。
- 启动清理逻辑必须按 execution_backend 隔离；redis 模式禁止启动时全量 reconcile_stale_chat_runs。

## 8. 工程改动清单

以下新增路径是实现时的建议组织方式。

| 文件/目录 | 改动 |
| --- | --- |
| backend/app/models/agent_run.py | 执行元数据、guard 与索引 |
| backend/app/models/chat_run_outbox.py（新增） | 待投递记录 |
| backend/app/services/chat_run_service.py | 原子创建、领取、续租、条件写入、取消、终态 |
| backend/app/services/chat_run_dispatch_service.py（新增） | Outbox 领取、投递对账、失联收尾 |
| backend/app/core/chat_runs.py | 抽取执行主体，保留 in_process 适配 |
| backend/app/core/chat_run_queue.py（新增） | Redis 客户端、group、读写、ACK、回收 |
| backend/app/core/agent_bootstrap.py（新增） | API/Worker 共享初始化与关闭 |
| backend/app/workers/chat_run_worker.py（新增） | 独立消费入口 |
| backend/app/workers/chat_run_dispatcher.py（新增） | 独立调度入口 |
| backend/app/api/chat.py、app/main.py、schemas/chat.py | 运行模式、取消语义、旧接口处理 |
| backend/app/api/session.py 及删除服务 | 执行占用检查 |
| backend/app/config.py、requirements.txt | redis.asyncio 依赖和集中配置 |
| backend/app/migrations/（新增） | 版本化迁移与升级入口 |
| frontend/src/components/ChatPanel/index.vue | 排队/取消/异常占用与恢复提示 |
| docker-compose.yml、环境模板、部署文档 | redis、dispatcher、worker、迁移步骤 |
| backend/tests/、frontend/tests/ | 确定性协议测试和故障集成测试 |

不默认引入 Celery；现有执行链已经是 asyncio，先用专用 Worker 复用它。保留 Windows SelectorEventLoop，入口放在 app 包内，确保现有 Dockerfile 的 COPY app 能包含入口。

## 9. 部署与配置

新增配置建议：CHAT_RUN_EXECUTION_BACKEND、REDIS_URL、CHAT_RUN_QUEUE_PREFIX、CHAT_RUN_WORKER_CONCURRENCY、CHAT_RUN_HEARTBEAT_SECONDS、CHAT_RUN_LEASE_SECONDS、CHAT_RUN_CANCEL_POLL_SECONDS、CHAT_RUN_RECONCILE_SECONDS、CHAT_RUN_SHUTDOWN_GRACE_SECONDS、CHAT_RUN_MAX_QUEUED。

- Redis 固定经过验证的镜像版本、启用 AOF 和数据卷，任务 Redis 使用 noeviction；故障后数据库 queued 对账负责重新投递。Redis 不暴露生产公网端口。
- Worker/dispatcher 复用 backend 镜像，分别设置模块启动命令。
- 覆盖镜像原有 HTTP healthcheck：Worker 不监听 8000。健康检查检查本进程主循环与依赖状态；不能沿用 backend 的 /health。
- API、Worker 使用相同的配置层、模型角色配置与 StorageService。local 存储模式挂同一个 backend_storage 卷；MinIO 模式保持同桶与权限配置。所有文件链路与 workspace 限制照旧。
- Worker 启动创建自己的数据库、checkpoint 和模型客户端；数据库连接池预算按进程总量核算。
- 优雅停机先停止领取，再等待当前任务；超过等待上限请求取消，无法确认清理完成则留待失联流程，不自动将运行任务变回 queued。
- Worker 独立配置 ObservationSink/OTel；指标出口显式部署。指标使用低基数 labels，记录投递积压、等待时长、运行数、取消延迟、续租失败、失联数；run_id 等只进允许的关联字段，不进 Prometheus labels。

## 10. 实施顺序与阶段门禁

1. 数据与契约：迁移、Run 原子状态操作、Outbox、guard、取消字段；先通过数据库并发测试。
2. 执行拆分：共享 runtime 初始化、独立 Worker、终态协议；用可阻塞的假 Agent 验证脱离 API 执行。
3. 可靠调度：Redis 投递、Pending 处理、queued 对账、租约与隔离；注入各个事务边界的崩溃。
4. 接入：API 模式切换、旧入口处理、取消/历史恢复前端、Compose、Windows 启动。
5. 上线准备：真实 PG+Redis 集成、人工耗时产物冒烟、发布和回滚演练。

建议作为一个独立 OpenSpec change：extract-chat-run-worker-phase-one。规范覆盖 durable-chat-runs、docker-deployment、external-observability；当前 MVP change 不直接改写为本批任务。实现提交遵循子模块先提交、根仓库再更新指针。

## 11. 验收矩阵

| 场景 | 必须观察到的结果 |
| --- | --- |
| Agent 执行时重启 API | 同一 Worker/Run 持续执行，重连补齐事件 |
| 浏览器断网/切换会话 | 执行不中止，游标续接无重复 token |
| API 提交事务前退出 | 无半条 Run 或孤立 Outbox |
| 提交后、XADD 前退出 | 调度器恢复并投递 |
| XADD 后、published 标记前退出 | 可重复交付，Agent 只进入一次 |
| queued 消息在 Redis 丢失 | 数据库对账重新投递并最终领取 |
| 两个 Worker 收到同一 Run | 仅一个数据库领取成功 |
| 同一 thread 并发提交 | 一个成功，一个明确冲突 |
| terminal 已提交但 ACK 丢失 | 重投只清理消息，不再次执行 |
| 模型长时间不吐 token | 心跳仍续租，不误判失联 |
| Worker 被终止 | 租约过期后 error+done，running 不自动重跑 |
| 旧 Worker 暂停后恢复 | Run 条件写入失败；guard 未确认前禁止新轮次 |
| queued / running / terminal 取消 | 分别立即取消、请求停止后收尾、幂等返回 |
| 取消与完成并发 | 一个确定终态，只有一个 done |
| 到达审批并确认 | waiting_approval 释放 Worker；新 Run 恢复原 interrupt |
| 删除执行中的会话或计划 | 冲突返回，无悬空执行输入 |
| redis 模式调用旧 stream | 不启动进程内 Agent |
| Windows 宿主机与 Compose 启动 | event loop、存储、健康检查均可用 |

锁、条件更新、唯一约束必须在真实 PostgreSQL 上验证，不能仅依赖 SQLite 或 mock。集成测试显式使用 pytest -m integration，且使用假模型控制故障点。默认 pytest、Ruff check/format、前端 chat-run 测试与 build 作为回归门禁；真实模型只做小范围端到端冒烟，不能替代并发故障测试。

## 12. 发布与回滚

1. 暂停新 Run 提交，排空现有 in_process Run；确认旧执行者停止。
2. 执行增量迁移，检查索引和回填。
3. 部署 Redis、dispatcher、Worker，验证消费与存储健康。
4. 启用 API redis 模式和前端提示，开放提交。
5. 用耗时请求演练 API 单独重启、重连及取消。

回滚时先暂停提交并排空或明确停止 redis Run，再切回 in_process。不能仅切环境变量就让旧进程接管 running Run；保留新表和元数据，避免破坏诊断证据。若回到不识别新模式的旧提交，必须确认不存在任何 active Run，因为旧启动逻辑会全量标失败。

## 官方参考

- Redis Streams：https://redis.io/docs/latest/develop/data-types/streams/
- XACK：https://redis.io/docs/latest/commands/xack/
- XAUTOCLAIM：https://redis.io/docs/latest/commands/xautoclaim/
- SQLAlchemy MetaData 与 schema 修改：https://docs.sqlalchemy.org/en/20/core/metadata.html

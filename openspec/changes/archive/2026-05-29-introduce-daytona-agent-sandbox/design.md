## Context

SmartClass 当前通过 `backend/app/core/workspace.py` 为产物子 agent 提供受控 workspace 工具，包括列文件、读写 UTF-8 文本、精确替换和执行 Python/Node 代码。代码执行已经抽象为 `ExecutionBackend`，默认实现 `LocalSubprocessExecutionBackend` 使用后端宿主机本地 `subprocess` 运行入口文件，并具备超时、输出截断、路径穿越防护和安装命令拦截。

这个抽象为引入 Daytona 提供了清晰切入点：第一阶段不改变 agent 可见的 workspace 工具契约，也不把业务文件链路迁移到远端沙箱，而是将 `run_workspace_code` 的执行环境替换为可配置的 Daytona sandbox 后端。现有本地 workspace 仍作为文件 source of truth，Daytona sandbox 只承担执行、隔离和输出回收。

## Goals / Non-Goals

**Goals:**

- 提供可配置的 Daytona 执行后端，让 agent workspace 代码在隔离 sandbox 中运行。
- 保持 `WorkspaceToolset` 对 agent 暴露的工具名、输入输出 JSON 结构和安全校验尽量稳定。
- 复用现有 `ExecutionBackend` 抽象，保留本地执行后端作为开发、测试或 Daytona 不可用时的 fallback。
- 将 sandbox 生命周期、网络策略、超时、输出截断、错误分类和日志字段纳入 SmartClass 治理体系。
- 确保生成产物最终同步回本地 artifact 链路，而不是停留在 Daytona 临时文件系统。

**Non-Goals:**

- 不在本次变更中迁移知识库文件、附件文件或 artifact 存储到 Daytona。
- 不把 Daytona preview URL 替代现有 HTML artifact iframe 预览。
- 不允许 agent 在运行时随意安装依赖；依赖应通过 Daytona snapshot/image 或后端部署环境治理。
- 不改变 LangGraph 主流程、审批节点或前端 SSE 事件契约。

## Decisions

### Decision 1: Daytona 作为 `ExecutionBackend` 实现接入

新增 `DaytonaExecutionBackend`，由 `WorkspaceManager` 通过配置选择。`WorkspaceManager.run_code` 继续负责解析本地 workspace 路径、读取入口文件、拦截安装命令；真正执行时委托给当前 backend。

Rationale:

- 当前代码已经有 `ExecutionBackend.execute(language, entrypoint, paths)` 的稳定扩展点。
- `WorkspaceToolset` 和 skill 文档无需立即改动。
- 测试可以同时覆盖本地后端和 Daytona 后端，便于回滚。

Alternatives considered:

- 替换整个 `WorkspaceManager` 为远端文件系统实现。隔离更彻底，但会影响 list/read/write/replace 全部工具，第一阶段风险更高。
- 在 agent 层直接调用 Daytona SDK。实现快，但会绕过 workspace 统一策略和审计，不符合当前治理方向。

### Decision 2: 本地 workspace 是 source of truth，执行前同步到 sandbox

Daytona 后端执行一次代码时：

1. 基于 `thread_id`、`run_id`、`plan_id` 和 `agent_name` 创建或获取 sandbox。
2. 将当前本地 `workspace_root` 中的必要文件上传到 sandbox workdir。
3. 在 sandbox 中设置 `AGENT_WORKSPACE_ROOT`、`AGENT_RUN_ROOT`、`AGENT_OUTPUT_DIR` 等环境变量。
4. 执行入口文件。
5. 下载 sandbox 中变更的输出文件到本地 `output_root` 或 `workspace_root`，再返回现有 `WorkspaceExecutionResult`。

Rationale:

- 保留现有文件读写语义，避免一次性迁移所有 workspace 操作。
- 本地 artifact 服务继续从本地 storage 收集输出。
- Windows 本地路径不会暴露给远端执行代码，远端只看到 POSIX 风格 sandbox 路径。

Alternatives considered:

- 每个 write/read 都直接操作 Daytona fs。长期可以考虑，但会让普通文本操作依赖外部服务可用性。
- 只上传入口文件。速度更快，但会破坏脚本读取同目录输入、模板或中间文件的能力。

### Decision 3: 沙箱生命周期默认短生命周期、可配置清理

默认按 run 创建短生命周期 sandbox，使用 Daytona label 标记 `app=smartclass`、`thread_id`、`run_id`、`plan_id`、`agent_name`、`purpose=workspace-code`。配置项控制 auto-stop、auto-archive、auto-delete、执行后 stop/delete 策略。

Rationale:

- 按 run 隔离最符合当前 agent workspace 安全边界。
- label 便于审计、定位和后台清理。
- 生命周期策略可以在开发环境和生产环境之间调整。

Alternatives considered:

- 按 thread 复用 sandbox。性能更好，但跨 run 状态残留风险更高。
- 永久 sandbox 池。吞吐更好，但需要额外调度、配额和清理机制，不适合作为第一阶段。

### Decision 4: 网络默认收敛，依赖通过 snapshot/image 预置

新增配置控制 Daytona sandbox 网络策略。生产默认应为阻断网络或显式 CIDR allow list。代码中继续保留安装命令拦截；需要的 Node/Python/Office 依赖通过 Daytona snapshot/image 预置。

Rationale:

- Agent 生成代码具备不确定性，默认联网会增加数据泄露和供应链风险。
- 当前 skill 已经要求不要运行 npm/pip 安装命令，Daytona 后端应保持一致。
- snapshot/image 能让产物生成环境可复现。

Alternatives considered:

- 默认开放网络。调试方便，但安全边界不清晰。
- 运行时临时安装依赖。灵活，但慢、不稳定且不可审计。

### Decision 5: 错误与日志按 SmartClass 结构化契约归一

Daytona API 错误、创建超时、执行超时、非零 exit code、网络策略失败、输出缺失和清理失败要映射为内部错误分类，并通过现有 progress 与 artifact trace 输出用户可理解摘要。

Rationale:

- SSE `error` 和 `artifact_trace` 不能泄露完整上下文或密钥。
- 产物生成失败必须能定位是模型、工具、权限、依赖、网络、超时还是输出缺失。

Alternatives considered:

- 直接透传 Daytona SDK 异常。排查方便但用户体验和安全性较差。

## Risks / Trade-offs

- [Risk] Daytona SDK、API 或云服务不可用导致产物生成失败 → Mitigation: 保留本地后端 fallback 配置，并把外部服务失败归类为可理解错误。
- [Risk] 每次执行上传整个 workspace 影响性能 → Mitigation: 第一阶段限制 workspace 文件数量/大小，后续可做增量同步或按 thread 复用 sandbox。
- [Risk] 远端 POSIX 路径与 Windows 本地路径差异造成脚本兼容问题 → Mitigation: 远端统一通过 `AGENT_*` 环境变量暴露路径，输出文件回收时统一转为 POSIX 相对路径。
- [Risk] sandbox 文件未同步回 artifact 链路 → Mitigation: 执行后强制扫描远端 output dir 并下载到本地 `output_root`，测试覆盖 output_files。
- [Risk] 开放网络造成数据外传 → Mitigation: 默认阻断网络或显式 allow list，网络策略必须来自配置层。
- [Risk] 清理失败造成资源泄露 → Mitigation: 设置 Daytona auto-stop/auto-delete，并记录 sandbox id 供后台补偿清理。

## Migration Plan

1. 新增 Daytona 配置项和依赖声明，但默认继续使用本地执行后端。
2. 实现 `DaytonaExecutionBackend` 与最小文件同步、执行、输出回收逻辑。
3. 增加单元测试和 mock Daytona client 测试，验证配置、本地 fallback、路径保护、超时、非零 exit、输出收集和清理策略。
4. 在开发环境启用 Daytona 后端，使用现有 PPT/DOCX/HTML 产物生成链路做端到端验证。
5. 生产启用前准备 Daytona snapshot/image，确认依赖、网络策略和生命周期配置。
6. 出现问题时通过配置切回本地执行后端；已生成产物仍沿用本地 artifact 链路，无需数据迁移。

## Open Questions

- 生产环境使用 Daytona Cloud 还是自托管/专用 target？
- 第一阶段默认是执行后 stop 还是 delete？开发和生产是否需要不同策略？
- 需要预置哪些依赖到默认 snapshot/image，尤其是 `pptxgenjs`、Office/PDF 工具链和字体资源？
- 是否需要为长时间产物生成增加后台任务级取消接口，而不只是依赖执行超时？

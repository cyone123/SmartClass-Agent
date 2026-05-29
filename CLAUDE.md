# SmartClass Agent `AGENTS.md`

## 1. 文档定位

本文件是仓库根目录的主规范，面向参与本项目的 AI 开发代理与工程师。

目标不是介绍产品，而是提供一份可直接驱动开发的执行文档，帮助 AI：

- 准确理解项目当前真实状态，而不是把 roadmap 当成已实现能力
- 在前后端、Agent、RAG、文件处理、产物生成与工程化治理之间保持一致的数据契约
- 优先做高价值、低歧义、可验证、可回滚的改动，减少返工和错误假设
- 在后续 Agent 增强中优先考虑稳定性、安全性、可观测性与评估闭环

由于沙盒环境和路径问题，读取代码时优先使用绝对路径。

## 2. 项目定位与当前阶段

SmartClass 是一个面向教师的多模态互动式教学智能体，目标是帮助老师完成备课、教学设计、教案生成、PPT 生成、互动内容生成与产物迭代修改。

当前项目已经从“主流程功能建设阶段”进入“Agent Harness 治理与工程化增强阶段”。

当前真实状态：

- 产品主流程已经基本打通：聊天、教学设计、知识库 RAG、附件分析、语音/视频输入、产物生成、产物预览、产物差量修改都已具备实现
- 后续重点不再是简单堆功能，而是提升 Agent 行为的可控性、稳定性、安全性与可评估性
- 工程化重点是补齐对象存储、结构化日志、链路追踪、可观测性、测试与评估基准，为持续迭代提供闭环

## 3. 当前技术栈与事实入口

### 后端

- FastAPI
- LangChain
- LangGraph
- PostgreSQL
- SQLAlchemy
- PGVector 风格 RAG
- OpenAI 兼容模型接口
- 本地文件存储与 Agent workspace

关键事实入口：

- [`backend/app/core/graph.py`](./backend/app/core/graph.py)
- [`backend/app/core/agent.py`](./backend/app/core/agent.py)
- [`backend/app/core/skills.py`](./backend/app/core/skills.py)
- [`backend/app/core/workspace.py`](./backend/app/core/workspace.py)
- [`backend/app/core/progress.py`](./backend/app/core/progress.py)
- [`backend/app/core/rag.py`](./backend/app/core/rag.py)
- [`backend/app/services/file_service.py`](./backend/app/services/file_service.py)
- [`backend/app/services/artifact_service.py`](./backend/app/services/artifact_service.py)
- [`backend/app/api/chat.py`](./backend/app/api/chat.py)
- [`backend/app/api/file.py`](./backend/app/api/file.py)

### 前端

- Vue 3
- Vite
- Element Plus
- Pinia
- OnlyOffice 文档预览
- SSE 流式聊天与 Agent 进度/产物事件消费

关键事实入口：

- [`frontend/src/components/ChatPanel/index.vue`](./frontend/src/components/ChatPanel/index.vue)
- [`frontend/src/components/ContextPanel/index.vue`](./frontend/src/components/ContextPanel/index.vue)
- [`frontend/src/components/FilePreviewPanel/index.vue`](./frontend/src/components/FilePreviewPanel/index.vue)
- [`frontend/src/api/file.js`](./frontend/src/api/file.js)
- [`frontend/vite.config.js`](./frontend/vite.config.js)

## 4. 仓库结构速览

```text
demo/
├─ backend/
│  ├─ app/
│  │  ├─ api/          # chat / file / plan / session 接口
│  │  ├─ core/         # graph、agent、rag、skills、llm、progress、workspace
│  │  ├─ models/       # SQLAlchemy 模型
│  │  ├─ schemas/      # API schema
│  │  └─ services/     # 业务逻辑
│  ├─ skills/          # docx / pdf / ppt-generator 等 skills
│  ├─ storage/         # 当前本地上传文件、附件、产物与 agent workspace
│  └─ tests/
└─ frontend/
   ├─ src/
   │  ├─ api/
   │  ├─ components/
   │  ├─ layout/
   │  ├─ router/
   │  └─ store/
   └─ AGENTS.md
```

## 5. 当前能力矩阵

### 已实现

- 教学计划、会话、知识库文件、附件、产物文件的基础 CRUD 与查询接口
- LangGraph 主流程：
  - 意图识别
  - 教学要素抽取
  - 信息不完整时追问并中断
  - 教学要素确认与教学设计确认
  - RAG 向量检索
  - 教学设计规划输出
  - 产物生成路由
  - 产物修改路由与目标澄清
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

### 已有但需要加强

- Agent 护栏已有基础 middleware 与 workspace 限制，但尚未形成完整策略体系
- 产物生成有 trace，但日志、指标、运行摘要与失败归因还不完整
- 文件仍以本地 storage 为主，尚未抽象为可替换对象存储
- 测试更偏功能验证，尚未形成 Agent 效果评估集、回归集和自动评分闭环
- 数据库 schema 存在启动期补丁式迁移逻辑，后续应逐步走显式迁移体系

## 6. 当前真实数据流

### 6.1 对话主链路

1. 前端通过 `/api/chat/stream` 发起请求。
2. 后端创建 `run_id`，先发送 `metadata` SSE 事件。
3. 后端根据 `thread_id` 找到会话与 `plan_id`。
4. 如果请求携带 `attachment_ids`，先走附件分析链路生成 `attachment_text`。
5. LangGraph 根据当前状态进入：
   - 普通聊天
   - 教学规划主流程
   - 产物修改流程
   - 审批中断恢复
6. 运行期间通过 SSE 推送 token、进度、产物、产物 trace、审批请求、错误等事件。
7. 结束时发送 `done`。

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

### 6.2 知识库文件链路

1. 上传到 `knowledge_files`。
2. 文件落到当前本地 `backend/storage`。
3. 后端异步入队。
4. `FileIngestionRuntime` 消费队列。
5. RAG runtime 做解析、切分、向量化与入库。
6. 前端轮询知识库文件状态并展示“待解析 / 特征解析中 / 已解析 / 失败”。

### 6.3 会话附件链路

1. 上传到 `attachment_files`。
2. 文件按 `plan_id + thread_id` 归属存储。
3. 发送消息时携带 `attachment_ids`。
4. 后端先做附件分析，再把摘要注入图输入。
5. 语音与视频附件有专门的转写/分析链路。

### 6.4 产物链路

1. 教学计划经用户确认后，可选择生成 `ppt`、`docx`、`html-game`。
2. 后端为每个产物创建 running 状态的 `ArtifactFile`。
3. 产物子 Agent 在 workspace 中执行 skill 或代码工具。
4. 生成结果复制到 `storage/artifacts/...`。
5. 产物状态更新为 `ready` 或 `failed`，并通过 SSE `artifact` 事件推给前端。
6. 产物修改会基于源产物创建 revision，并维护 `parent_artifact_id`、`root_artifact_id`、`revision_number`、`is_current`。

## 7. 下一阶段开发重点

### 7.1 Agent 护栏与治理

后续新增 Agent 能力时，优先把它纳入可治理框架，而不是只追加 prompt 或工具。

优先方向：

- 明确每类 Agent 的职责边界：主流程 Agent、附件分析 Agent、产物生成 Agent、产物修改 Agent、评估 Agent
- 为工具建立分级权限：
  - 只读工具
  - workspace 写工具
  - 代码执行工具
  - 文件/对象存储写工具
  - 外部网络或未来第三方 API 工具
- 为高风险动作增加显式审批或策略判定：
  - 覆盖已有产物
  - 批量生成或长耗时任务
  - 访问外部 URL
  - 执行代码
  - 读取或写入非当前 thread/plan 的文件
- 统一工具调用审计字段：`run_id`、`thread_id`、`plan_id`、`agent_name`、`tool_name`、输入摘要、输出摘要、耗时、状态、错误
- 对模型输出做结构化校验，关键节点优先使用 Pydantic/schema 验证
- 对 Agent 失败做可分类的错误建模：模型错误、工具错误、权限错误、用户输入不足、文件处理失败、超时、外部服务失败
- 保留 human-in-the-loop，不要为了自动化绕过确认节点

### 7.2 Agent 效果评估与闭环

后续应建立可重复执行的 Agent evaluation harness，用于判断系统是否真的变稳。

建议评估维度：

- 意图识别准确率：普通聊天、教学规划、产物修改是否分流正确
- 教学要素抽取质量：学科、年级、主题、课时、重点难点、目标是否完整且不幻觉
- 追问质量：信息不足时是否问关键缺口，而不是过度追问
- RAG 质量：检索内容是否相关、是否被正确引用到教学设计
- 产物生成成功率：是否产出合法文件、文件是否可打开、是否与教学计划一致
- 产物修改准确率：是否改对目标产物、是否保留未要求修改的内容
- 安全性：是否拒绝越权文件访问、危险命令、未授权工具使用
- 稳定性：超时、重试、失败状态是否可追踪且前端可见

建议落地方式：

- 建立 `backend/tests/evals/` 或等价目录存放评估用例
- 每个用例至少包含：输入、上下文、期望路由、关键断言、允许的模糊匹配规则
- 对非确定性模型输出使用 rubric + 结构化断言结合，不只做字符串快照
- 把失败样本沉淀为回归集，不把一次人工验证当成长期保障
- 评估结果要能关联 `run_id` 与 trace，便于定位失败原因

### 7.3 工程化增强

后续工程化优先级：

- 对象存储抽象：
  - 不要在业务代码里继续散落 `Path(storage_path)` 直接读写
  - 抽象 `StorageBackend` 或等价服务，先兼容本地文件，再接入 S3/MinIO/OSS
  - 数据库中保留稳定 storage key，URL、签名、公开访问策略由存储服务生成
- 日志系统：
  - 从零散 `print` 迁移到结构化 logging
  - 日志必须带 `run_id`、`thread_id`、`plan_id`，必要时带 `artifact_id`
  - 避免记录完整用户隐私内容、完整附件内容、完整模型上下文
- 可观测性：
  - 记录 Agent 节点耗时、工具耗时、失败类型、token 使用、产物生成耗时
  - 为 SSE 生命周期、文件入库、产物生成、OnlyOffice 回调建立可追踪事件
  - 后续可接入 OpenTelemetry 或 LangSmith 类工具，但不要把第三方平台写死进核心业务
- 后台任务：
  - 文件入库、视频分析、产物生成等长任务应逐步具备任务状态、重试、取消与幂等能力
- 配置治理：
  - 所有模型、存储、日志、外部服务配置必须来自配置层或环境变量
  - 不在业务代码中硬编码本地机器路径、外部地址或密钥

## 8. 关键现实约束

### 8.1 模型与 skill 约束

- 当前后端实际模型封装在 [`backend/app/core/llm.py`](./backend/app/core/llm.py)，使用 OpenAI 兼容接口
- skill 风格参考 progressive disclosure，但运行时不是 Anthropic SDK
- AI 不要把“Anthropic 风格 skill 文档”误判为“Anthropic 模型运行时”
- 涉及 Office、PDF、PPT 的处理优先复用现有 skill/script，而不是直接让模型裸处理二进制内容

### 8.2 文件链路约束

- `knowledge_files`、`attachment_files`、`artifact_files` 是三条不同链路
- `knowledge_files` 面向知识库和 RAG
- `attachment_files` 面向单次或多轮会话上下文分析
- `artifact_files` 面向 Agent 生成和修改后的用户可见产物
- 任何新增多模态能力都必须先明确属于哪条链路，不能混用

### 8.3 Agent workspace 约束

- workspace 是 Agent 产物生成与 skill 执行的受控工作区，不等同于项目源码目录
- Agent workspace 工具只能访问当前 thread/run 下的 workspace 路径
- workspace 代码执行已有超时、输出截断与安装命令限制；新增执行能力必须继承这些约束
- 不允许通过 shell 绕过 workspace 工具策略
- 产物子 Agent 输出必须最终进入 artifact 链路，不应只停留在临时 workspace

### 8.4 平台与工具约束

- 当前项目运行环境对 Windows 友好
- Shell、路径、OnlyOffice 接入都应保持 Windows 兼容
- 不要默认依赖 Linux-only 的处理方式
- 文件路径展示与存储 key 要考虑 Windows 分隔符和跨平台序列化

### 8.5 Git 与工作区约束

- 提交前先确认当前 git 根目录与工作区状态
- 不要假设这是一个绝对干净、单一边界的 monorepo
- 前后端目录的提交边界、权限状态、safe.directory 状态都可能需要先确认
- 不要回滚用户已有改动，除非用户明确要求

### 8.6 编码与文本约束

- 文本、提示词、文档默认使用 UTF-8
- 如果出现中文乱码，优先处理编码问题，不要在乱码文本上继续堆功能
- 面向用户的中文提示词要保持清晰、可执行，避免过度抽象

## 9. AI 开发原则

- 先补数据契约，再补 UI 细节
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
- `error` 事件要给出用户可理解信息，同时后台日志保留可排查细节
- `done` 只表示本次 SSE 流结束，不等同于所有后台任务永久成功

### 10.2 统一产物对象契约

所有产物生成结果统一抽象为 artifact，至少包含：

```ts
type Artifact = {
  id: string | number
  type: "ppt" | "docx" | "html-game" | "pdf" | "other"
  title: string
  status: "pending" | "running" | "ready" | "failed"
  mime_type?: string
  extension?: string
  size_bytes?: number
  storage_path?: string
  url?: string
  preview_url?: string
  plan_id?: number
  thread_id?: string
  parent_artifact_id?: number | null
  root_artifact_id?: number | null
  revision_number?: number
  is_current?: boolean
  error_message?: string | null
  created_at?: string
  updated_at?: string
}
```

约束：

- 前端展示以 artifact 对象为准，不从聊天文本中猜测产物
- 修改产物必须保留版本关系
- `ready` 前不应暴露下载 URL
- `failed` 必须能展示失败原因的用户可读摘要

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
- 工具输入输出只记录摘要或必要字段

### 10.5 文件与存储契约

后续从本地文件升级到对象存储时，业务层应依赖稳定存储接口：

```ts
type StoredObject = {
  key: string
  filename: string
  mime_type: string
  size_bytes: number
  sha256?: string
  url?: string
}
```

约束：

- 数据库可继续保留 `storage_path` 以兼容当前实现，但新增代码应优先通过存储服务访问
- URL 生成不应散落在业务逻辑中
- 删除、覆盖、回写必须考虑知识库文件、附件、产物三条链路的不同语义

## 11. 变更验收清单

### 后端

- API schema 是否同步更新
- graph 是否接入新状态或新节点
- Agent 工具权限、审批、错误分类是否明确
- 文件处理链路是否与 `knowledge_files` / `attachment_files` / `artifact_files` 正确对应
- 失败状态是否可追踪、可返回、可展示
- 是否保留 `run_id`、`thread_id`、`plan_id` 的日志关联
- 是否新增或更新必要测试
- 涉及 Agent 行为变化时，是否增加评估用例或回归样本

### 前端

- 消息渲染是否兼容旧事件与新事件
- 进度卡片是否来自真实后端事件
- 产物展示是否接入统一 artifact 模型
- 审批卡片是否能正确恢复中断
- 产物 trace 是否做长度与布局保护
- 错误、失败、空状态是否可理解
- 回退兼容是否保留

### Agent 与评估

- 是否明确新增能力属于哪个 Agent 或 graph 节点
- 是否明确可用工具与禁止工具
- 是否有最小可复现用例
- 是否能通过评估集或回归测试证明没有破坏旧能力
- 是否能从日志或 trace 中解释失败原因

## 12. 协作建议

- 开工前先读本文件，再读对应模块入口文件
- 对话、进度、产物、附件、审批、trace 这几类能力优先看成“协议问题”，其次才是 UI 问题
- 需求不明确时，优先做对后续演进最稳的抽象，不做一次性特判
- 任何新增功能都应说明：
  - 属于哪条链路
  - 复用了哪些已有能力
  - 输出遵循什么契约
  - 是否需要护栏
  - 如何测试或评估
- 新阶段开发时，默认把“Agent 行为是否可控、可测、可观测”放在和“功能是否跑通”同等重要的位置

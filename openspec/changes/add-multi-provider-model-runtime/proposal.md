## Why

SmartClass 当前将聊天角色与 OpenAI Chat Completions 客户端绑定，无法直接使用 Anthropic Messages 或 Gemini 原生协议；角色逐字段回退、模块级模型绑定也会阻碍后续动态配置。需要建立统一且可版本化的后端模型接入边界，让不同提供商参与现有教学、工具调用、记忆及视觉流程，并保留未来管理界面的接入路径。

## What Changes

- 分离协议、提供商预设、认证连接、模型配置与业务角色；使用声明式 YAML 和环境变量凭据引用，保留旧环境变量兼容入口。
- 提供 OpenAI Chat Completions、Anthropic Messages、Gemini Developer API generateContent 三条协议路径，以及 OpenAI、Anthropic、Google Gemini、OpenRouter、DeepSeek、智谱和自定义连接预设。
- 以 LangChain 原生集成为基础，实现角色解析、能力校验、参数映射、模型工厂、客户端生命周期和统一错误分类；复用已有 ModelRuntime。
- 迁移主图、产物/附件 Agent、记忆、压缩及视频视觉入口，清除模块加载时固定的模型与工具绑定。
- 固定运行和教学工作流的模型配置快照，覆盖审批恢复、并行产物和后台反思；预留配置仓库、密钥解析与公开配置 DTO 接口。
- 验证工具多轮交互、结构化输出、thinking 元数据、流式展示、checkpoint 与压缩；保持现有审批和 SSE 语义。
- 增加离线协议契约测试、真实提供商 smoke、业务回归与脱敏的实际模型配置证据。
- 本期配置在启动时加载，修改后重启生效。不实现前端设置页、管理 CRUD/发布 API、热更新、多租户自带密钥、独立网关、模型自动选优，或新的 embedding/STT 提供商。
- **BREAKING（配置兼容性收紧）**：旧配置完整有效时保留行为；凭据/端点跨角色拼接、无效显式配置和不支持的能力组合将明确失败，不再静默补齐或降级。

## Capabilities

### New Capabilities

- `model-provider-configuration`: 可版本化的提供商、连接、模型与角色配置，旧环境变量迁移、完整配置继承、凭据引用和能力描述。
- `multi-protocol-model-runtime`: 三种协议的统一接入、角色工厂、工具与消息兼容、流式处理、失败策略及后台调用一致性。

### Modified Capabilities

- `durable-chat-runs`: 新增运行配置快照与跨审批恢复的工作流版本固定要求。
- `context-compression`: 新增跨协议历史完整性、原生元数据保留和压缩角色快照要求。
- `evaluation-harness-integrity`: 扩展报告中的实际角色/协议/配置版本元数据，以及提供商兼容证据的口径。

## Impact

- 后端：`app/core/llm.py`、`model_runtime.py`、`graph.py`、`agent.py`、`memory.py`、`context_compression.py`、`video_transcribe.py`、`observability.py`、配置层、运行服务与反思 worker。
- 持久化：新增可空的运行模型配置快照字段；扩展 graph state 和反思任务快照 schema，提供旧记录兼容策略。密钥不进入这些快照。
- 依赖：增加 Anthropic、Google GenAI 的 LangChain 集成，按契约验证结果决定 DeepSeek 专用集成；收敛经过验证的依赖版本。
- 部署与证据：根目录配置示例、Compose 配置挂载、README、后端测试、评估 manifest 和 benchmark 脱敏 allowlist。
- 前端和现有外部聊天 API 不新增配置操作或协议专用事件。embedding/STT 保持现有实现与独立边界。
- 实施分五阶段：配置与工厂 → 入口迁移与快照 → 原生协议 → 提供商预设 → 发布验证。业务代码位于 backend 子模块，实施提交时先提交子模块，再更新根仓库指针。

**SmartClass Agent 智能教学助手平台**

**2026.03 - 2026.06**

https://github.com/cyone123/SmartClass-Agent

**技术栈**：`FastAPI`、`LangGraph`、`LangChain`、`PostgreSQL/PGVector`、`MinIO`、`JWT`、`OpenTelemetry`、`Prometheus`、`Vue 3`、`OnlyOffice`

面向教师备课中“资料分散、教案/课件制作耗时、生成内容难以持续迭代”等问题，构建智能 Agent 平台，打通从教学需求输入、教学设计，到课件生成、预览和差量修改的端到端流程。

- 基于 LangGraph 固定 **Workflow + Sub-Agent** 混合架构设计可控 Agent 流程，主 Workflow 保障流程确定性、审批中断和状态恢复，Sub-Agent 负责复杂产物生成与修改，兼顾可控性与扩展性。
- 设计 Profile（稳定画像）+ Experience（动态经验）双层**长期记忆**，支持长期记忆的自动检索、反思写入、更新及前端 CRUD 管理，提升备课任务的个性化与 Agent 的持续学习能力。
- 针对教师长程备课场景设计**上下文压缩策略**，当 Token 窗口超过阈值时自动总结历史消息，仅保留近期对话、教学元数据及生成状态，使长线程仍能保持上下文一致性。对待审批/中断场景自动跳过，避免破坏流程一致性。
- 设计 **Harness** 执行层，对 Skill 和工具调用进行权限校验、路径白名单校验、超时中断、输出截断及失败重试，使 Agent 执行更稳定、安全。
- 实现 **Sub-Agent 沙箱**执行能力，支持本地 workspace 与 Daytona 云沙箱双执行后端，统一管理文件同步、代码运行、超时控制和资源清理，降低模型生成代码或处理复杂文件时对宿主环境的风险。
- 建设 Agent **可观测性与评估闭环**，采集 LLM请求、Tool 调用、Workflow 耗时等指标，并沉淀 **24 个 评估用例**，用于定位失败原因和防止核心 Agent 行为回退。
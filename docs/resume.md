
**SmartClass Agent 智能教学助手平台**
**2026.03 - 2026.16**

<https://github.com/cyone123/SmartClass-Agent>

独立设计并实现多模态教学 Agent 平台，覆盖“需求澄清—教学设计—知识检索—产物生成—在线预览—差量修改”完整流程，重点解决长程 Agent 的状态治理、可控执行、产物生成与工程可观测问题。

**技术栈：** `FastAPI`、`LangGraph`、`LangChain`、`PostgreSQL/pgvector`、`MinIO`、`OpenTelemetry`、`Prometheus`、`Vue 3`、`OnlyOffice`

- 基于 **LangGraph** 设计确定性 Workflow 与产物 Sub-Agent 协同架构，通过状态机统一编排意图识别、要素抽取、RAG 与产物路由，并使用 Checkpoint 实现 **3 类 Human-in-the-loop 审批中断与恢复**。

- 设计 **用户画像+ 经验 双层长期记忆机制**，通过 Namespace 实现用户级隔离，并支持记忆检索、反思写入、冲突更新、确定性脱敏与可视化管理；8 个真实模型记忆场景全部通过验证。

- 针对长程 Agent 设计**上下文压缩机制**，保留结构化任务状态与近期对话；在 30/50/100 轮合成长对话实验中，累计 Prompt Token 量净降低 **21.2%–70.6%**。

- 构建 **PPTX、DOCX、HTML** 三类 Artifact 生成与 Revision 差量修改链路，统一接入 SSE 与 MinIO；30 次跨学科真实模型实验中 **29 次产物可用（96.7%）**。

- 建设受控 **Agent Harness**，通过 Policy Middleware 管理 Skill/Tool 权限，并实现路径穿越防护、执行超时、输出截断、失败重试与依赖安装约束；抽象本地 Workspace 与 Daytona 云沙箱双执行后端，实现模型生成代码与宿主环境隔离。

- 建立覆盖 LLM、Tool、RAG、Workspace 的可观测与评估体系，以统一 RunContext 串联结构化日志、OpenTelemetry Trace 与 Prometheus Metrics；沉淀 24 个评估用例，真实模型基线通过率 **95.8%**。

- 对认证 SSE 链路进行分层性能测试，累计完成约 **2.6 万次请求**；Mock LLM 场景零失败、完整请求 p95 ≤ 590ms，真实模型 8 路并发成功率 **99.1%**，通过 Trace 将主要失败定位至上游流式响应超时。

**SmartClass Agent 智能教学助手平台**

**2026.03 - 至今**

[github.com/cyone123/SmartClass-Agent](https://github.com/cyone123/SmartClass-Agent)

**技术栈**：`FastAPI`、`LangGraph`、`LangChain`、`PostgreSQL/PGVector`、`MinIO`、`OpenTelemetry`、`Prometheus`、`Vue 3`、`OnlyOffice`

面向教师备课资料分散、教案与课件制作耗时、生成内容难以持续迭代等痛点，独立设计并实现多模态教学 Agent 平台，打通“需求澄清—教学设计—知识检索—产物生成—在线预览—差量修改”全流程。

- 基于 **LangGraph** 设计确定性 Workflow 与产物 Sub-Agent 协同架构，以状态机编排意图识别、要素抽取、RAG 和产物路由；通过 Checkpoint 支持 **3 类 Human-in-the-loop 审批中断与恢复**，兼顾复杂任务自治与关键环节可控。
- 设计 **Profile + Experience 双层长期记忆**，按用户 Namespace 隔离并实现检索、反思写入、冲突更新及可视化 CRUD；引入写入资格门和确定性脱敏，阻止闲聊及敏感临时信息沉淀，**8 个真实模型记忆用例全部通过**。
- 面向长程备课设计上下文压缩机制，保留结构化教学状态与近期对话；在 30/50/100 轮合成长对话 A/B 实验中，计入摘要调用开销后累计 Prompt Token 估算量净降低 **21.2%/43.2%/70.6%**，18/18 次真实模型压缩成功，结构化状态与近期 6 轮消息保留率 **100%**。
- 构建 **PPTX、DOCX、HTML** 三类产物生成与 Revision 差量修改链路，统一接入 Artifact、SSE 和 MinIO 存储体系；30 次跨学科真实模型实验中 **29 次产物可用（96.7%）**，PPTX/HTML 均为 **10/10**，唯一失败通过 Trace 定位为 DOCX 生成超时。
- 建设受控 **Agent Harness**：以 Policy Middleware 约束 Skill/Tool 权限，提供路径穿越防护、执行超时、输出截断、失败重试及依赖安装限制；抽象本地 Workspace 与 **Daytona 云沙箱**双执行后端，统一文件同步、代码执行和资源回收，隔离模型生成代码对宿主环境的影响。
- 搭建贯穿 LLM、Tool、RAG、Storage、Workspace 与 Artifact 的可观测体系，以统一 RunContext 串联结构化日志、OpenTelemetry Trace 和 Prometheus Metrics；沉淀 **6 类 24 个评估用例**及分类回归门禁，真实模型基线 **23/24 通过（95.8%），运行错误率 0%**。
- 建立认证 SSE 链路的分层压测与故障归因机制：24 个 Locust 窗口累计 **26,128 次请求**，Mock LLM 下 24,457 次请求零失败、完整请求 p95 ≤ 590ms；真实 DeepSeek 在 1/2/4 路并发下零失败、TTFT p95 ≤ 2.8s，8 路成功率 **99.11%**，并将失败归因至上游 120s 无流式 Chunk 超时。

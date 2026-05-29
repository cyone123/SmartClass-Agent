我查了最新的 Harness Engineering 资料。这里先说明一句：它目前更像 2026 年 AI Agent 工程领域形成中的“实践标准”，不是 ISO 那种正式标准。参考点主要来自 OpenAI 的 Harness Engineering 文章、Agents SDK 的 guardrails/tracing 文档，以及近期关于 evaluation harness 的工程文章。

**核心判断**
从 AI Agent 开发技术角度看，SmartClass 下一阶段不只是“增强某个 Agent 能力”，而是要把它升级成一个有 Harness 的教学 Agent 平台：

> Agent = Model + Harness  
> 模型负责推理，Harness 负责上下文、工具、权限、观测、验证、回滚、评测和长期一致性。

当前项目已经有很好的基础：`LangGraph`、`SkillRegistry`、`Workspace`、`artifact trace`、SSE 事件、审批中断、产物版本链。下一阶段重点应该是把这些能力制度化、协议化、可验证化。

**参考标准提炼**
结合最新 Harness Engineering 实践，可以抽象成 7 个标准层：

1. Context：仓库知识与业务知识必须成为 Agent 可读的系统事实源  
2. Control：架构边界、工具权限、产物状态、事件协议要机械执行  
3. Agency：Agent 能调用哪些工具、何时调用、调用后如何验证，要有明确契约  
4. Runtime：Agent 执行过程要支持超时、重试、取消、恢复、回滚  
5. Guardrails：输入、输出、工具调用都要有拦截和 tripwire  
6. Observability：LLM、工具、RAG、Graph 节点、artifact 生成都要可追踪  
7. Evaluation：每次模型、prompt、skill、RAG、产物生成修改都要能回归评测

OpenAI 的文章特别强调：不要把 `AGENTS.md` 写成巨型说明书，而应让它成为目录，真正的系统事实源放在结构化 `docs/` 中，并用 linter/CI 检查文档、架构和约束是否过期。它还强调让 UI、日志、指标、trace 对 Agent 可读，从而让 Agent 能自己复现、验证和修复问题。  
来源：OpenAI Harness Engineering: https://openai.com/index/harness-engineering/

## **一、Agent 工具与 Skill Harness**
当前 `SkillRegistry + Workspace` 已经很接近 Harness 思路。下一步应把 tool 从“能调用”升级为“可治理调用”：

- 每个 tool/skill 定义 JSON Schema 输入输出
- 每个 tool 标记权限等级：read、write、generate、external_call、destructive
- 每次工具调用记录：`run_id`、`tool_name`、输入摘要、输出摘要、耗时、状态
- 工具调用前校验：路径、文件类型、大小、所属 plan/thread
- 工具调用后校验：产物是否存在、格式是否正确、是否越权写入
- 对 Python/Node 执行继续维持 workspace 沙箱，增加 CPU/时间/输出大小预算

建议新增一个 `ToolInvocation` 数据模型或日志表，把 Agent 的真实行为沉淀下来。

## **二、LangGraph Runtime Harness**
SmartClass 的核心是 LangGraph，因此应该为 graph 建立运行时标准：

- 每个节点定义输入状态、输出状态、失败状态、可重试性
- 每个节点发出标准 progress step
- 每次 graph run 都有唯一 `run_id`
- 支持用户取消正在生成的 artifact
- 支持长任务超时后进入 `failed/retryable`
- 支持服务重启后恢复 pending/running 任务
- approval 节点持久化，避免刷新页面后丢失上下文

可以把 graph 节点视为“Agent 操作系统中的进程”，而不是普通函数。

## **三、Guardrails 规划**
OpenAI Agents SDK 文档把 guardrails 分为输入、输出和工具调用层，并支持 tripwire 中止执行。这个思想可以直接迁移到当前项目。  
来源：OpenAI Guardrails: https://openai.github.io/openai-agents-js/guides/guardrails/

建议增加三类 guardrail：

- Input Guardrail：检测空请求、恶意提示注入、越权文件引用、超长输入、敏感信息
- Tool Guardrail：拦截危险路径、非法扩展名、跨 thread/plan 访问、异常外部 URL
- Output Guardrail：检查教学内容是否空泛、是否缺少引用、artifact 是否格式有效、是否包含不当内容

特别是 RAG 和附件链路，要加 prompt injection 防护：附件内容只能作为资料，不允许覆盖系统规则或工具权限。

## **四、Evaluation Harness**
这是企业级 Agent 项目最容易缺的一层。参考 evaluation harness 的实践，生产 AI 不应只在 CI 测一次，而要持续验证输入、输出、指标、漂移和回归。  
来源：Evaluation Harness: https://www.dilr.ai/blog/evaluation-harness-engineering

建议建立 5 类评测集：

- 意图识别评测：普通聊天、备课、修订、附件分析、无关请求
- 教学元数据抽取评测：学科、年级、主题、课时、重难点、目标
- RAG 评测：检索命中率、引用准确性、无资料时是否承认不足
- 产物生成评测：PPT 页数、结构、教学目标覆盖、文件可打开
- 差量修订评测：是否只改目标内容、是否保留原版风格、版本链是否正确

建议每个评测样例包含：

```ts
type AgentEvalCase = {
  id: string
  task_type: "route" | "metadata" | "rag" | "artifact" | "revision"
  input: unknown
  expected: unknown
  rubric: string[]
  required_tools?: string[]
  forbidden_tools?: string[]
}
```

短期先做 30-50 个 golden cases，后续从真实失败案例中沉淀。

## **五、Observability Harness**
OpenAI Agents SDK tracing 文档强调 trace 应覆盖 LLM generation、tool call、handoff、guardrail、自定义事件。  
来源：OpenAI Tracing: https://openai.github.io/openai-agents-js/guides/tracing/

当前项目已有 `artifact_trace`，但它更偏用户可视化。建议再增加工程 trace：

- `chat.stream.request`
- `graph.node.intent_route`
- `graph.node.metadata_extract`
- `rag.retrieve`
- `attachment.analyze`
- `llm.call`
- `tool.invoke`
- `artifact.generate`
- `artifact.revise`
- `onlyoffice.callback`

每个 span 记录：

- 耗时
- token 消耗
- 模型名称
- 输入输出大小
- 成功/失败
- 错误类型
- plan_id/thread_id/run_id/artifact_id

这样以后可以回答非常关键的问题：到底是 RAG 慢、模型慢、文件解析慢，还是产物 Agent 卡住了。

## **六、近期路线图**
第一阶段：Harness 基础化，2-3 周

- 精简 `AGENTS.md`
- 建立 `docs/` Agent 知识库
- 固化 SSE、artifact、progress、approval 协议文档
- 为 LangGraph 节点补状态契约
- 为 skill/tool 补输入输出 schema 和权限等级

第二阶段：Guardrail + Trace，3-5 周

- 增加 input/output/tool guardrails
- 增加统一 `run_id`
- 接入结构化日志和 OpenTelemetry 风格 trace
- 分离用户可见 artifact trace 与工程诊断 trace
- 建立模型调用、RAG、工具调用成本统计

第三阶段：Evaluation Harness，4-8 周

- 建立 golden eval cases
- 增加教学设计质量 rubric
- 增加 artifact 文件有效性自动检查
- 增加差量修订回归测试
- 把 eval 接入 CI 和日常开发流程

第四阶段：Agent 自验证与半自治，8 周以上

- 让 Agent 自动运行相关测试
- 让 Agent 自动读取 trace 判断失败原因
- 让 Critic Agent 审核产物质量
- 让 Eval Agent 给出是否可交付结论
- 最终形成“生成-验证-修复-再验证”的闭环

**最终目标**
SmartClass 的 AI Agent 技术目标可以定义为：

> 建立一个面向教学工作流的 Agent Harness，使模型、工具、知识库、产物生成、人工审批、评测与可观测性形成闭环，让每一次备课生成都可解释、可验证、可恢复、可持续改进。

换句话说，下一步不要只追“更强模型”或“更多功能”，而是把项目升级成一个真正有 Harness 的 Agent 系统。模型会换，prompt 会变，但 Harness 会成为这个项目的长期工程资产。
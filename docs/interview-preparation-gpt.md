# SmartClass Agent 面试准备手册



> 本文基于 `resume.md`、当前仓库实现、测试、OpenSpec 与已晋升/留存的 benchmark 证据整理。目标不是背诵代码，而是能讲清：为什么这样设计、实际怎么实现、证据如何测得、边界在哪里。



## 0. 面试前先修正的简历口径



| 原表述 | 核查结论 | 面试中的严谨说法 |

| --- | --- | --- |

| `2026.03 - 2026.16` | 月份 `16` 非法；仓库最早提交为 2026-04-03 | 按真实经历改成如 `2026.04 - 至今`，不要保留非法日期 |

| 独立的意图识别、要素抽取节点 | 当前主图已演进为 `conversation_entry_agent` + `teaching_intake_agent`，旧节点未注册 | “主图统一编排意图识别与教学要素收集”，不要再画旧拓扑 |

| 3 类 HITL 审批中断 | 代码有 4 个可恢复 interrupt 点；其中 3 个会形成审批卡，另 1 个是普通自由文本澄清 | “4 个可恢复中断点，覆盖需求/修改目标澄清、教学要素确认与教学方案确认” |

| Revision 差量修改 | 系统基于原文件做 targeted edit，但对象存储仍保存完整新版本，不存二进制 diff | “基于原产物的版本化增量迭代”，不要声称系统保证最小 diff |

| Local/Daytona 实现宿主隔离 | Daytona 是独立沙箱；Local 只是宿主受控子进程 | “生产可切到默认断网的 Daytona 隔离执行；Local 用于开发和测试” |

| 24 个真实模型用例通过率 95.8% | 24 例是 mixed：20 个模型用例、4 个确定性压缩用例；总体 23/24=95.83%，模型用例为 19/20=95% | “24 例混合基线 23/24 通过，其中 20 例使用真实模型” |

| 30 次产物实验 96.7% 可用 | 是自动化结构、解析和确定性 rubric 下的可用率；没有 Office 视觉 QA 或教师盲评 | 主动说明“29/30 通过自动化技术与内容结构门禁” |

| SSE 压测定位上游超时 | 26,128 次压测针对兼容接口 `/api/chat/stream`；正式 Live gate 为 FAIL；7 个失败中 3 个有明确 120 秒无 chunk 证据 | 说“已捕获主要异常指向上游流式超时”，不要声称 7 个失败全部被 Trace 证明 |



## 1. 项目总述



### 30 秒版本



SmartClass Agent 是一个面向教师的多模态备课智能体。我用 FastAPI 和 LangGraph 把需求理解、教学要素收集、知识检索、教学设计、人工确认以及 PPTX、DOCX、HTML 生成串成可暂停恢复的状态机；开放式产物制作交给受控 Sub-Agent。系统用 PostgreSQL/pgvector 管业务状态和检索、MinIO 管文件、Redis Streams + SSE 管可续传事件、OnlyOffice 管预览，并用长期记忆、上下文压缩和统一可观测体系解决长程 Agent 的状态、成本、安全与定位问题。



### 2 分钟版本



项目的核心思路是把“确定性的业务控制平面”和“概率性的模型执行平面”分开。主图先加载有界用户画像，入口 Agent 在普通对话、教学设计和产物修改之间做受约束分流；教学请求进入 Intake Agent 多轮补齐要素，教师确认后并发准备 RAG 与任务级 Experience，再由 Planner 生成教学方案并二次确认，最后按选择 fan-out 到三类 Artifact Agent 并由 fan-in 汇总。修改请求会先确定目标，必要时通过 HITL 澄清，然后从旧产物创建新 revision，而不是覆盖历史。



工程层面，我把产物 Agent 统一放进 AgentRuntime：Skill 按需披露，Policy Middleware 在工具执行前做授权，Workspace 工具限制文件边界、执行时间、输出和依赖安装，生产可把模型代码放进 Daytona 隔离沙箱。交互层采用“POST 创建后台 Run + GET SSE 订阅”的两阶段协议，PostgreSQL 保存 Run 生命周期，Redis Streams 保存可回放事件，浏览器断开不会取消任务。最后用 RunContext 串联 LLM、Tool、RAG、Workspace 的日志、Trace、Metrics，并用评估集、A/B benchmark 和分层压测形成可追溯证据。



### 一张图讲清主流程



```text

Vue 工作台 / JWT

​        |

POST 创建 Run ---- PostgreSQL: Run / Checkpoint / 业务状态

​        |

Profile -> Entry Agent

​           | 普通问答 -> END

​           | 教学设计 -> Intake -> 澄清 -> Metadata Review

​           |                         |

​           |                  RAG || Experience

​           |                         |

​           |                    Planner -> Plan Review

​           |                                  |

​           |                         PPT / DOCX / HTML

​           |                                  |

​           |                                fan-in

​           |

​           + 产物修改 -> 目标澄清 -> Revision Agent -> fan-in



事件 -> Redis Streams -> 可续传 SSE -> token / progress / approval / artifact

文件 -> StorageService -> Local 或 MinIO -> OnlyOffice / HTML Preview

```



---



## 2. 第 1 条：LangGraph Workflow、Sub-Agent 与 HITL



> 基于 LangGraph 设计确定性 Workflow 与产物 Sub-Agent 协同架构，通过状态机统一编排意图识别、要素抽取、RAG 与产物路由，并使用 Checkpoint 实现 3 类 Human-in-the-loop 审批中断与恢复。



### 应该怎样介绍



这里的“确定性”不是说 LLM 输出确定，而是说拓扑、允许动作、状态字段、审批边界、失败分支和副作用时机由代码固定。LLM 只负责语义判断与内容生成。当前入口 Agent 只能产生普通可见文本、开始教学设计、修改产物，或一次受限的 Experience 查询；动作经过本地 schema 校验，不能靠任意自由文本跳节点。



教学设计进入有界 Intake：只有字段完整时才一次性物化 canonical `teaching_metadata`，不会让半成品元数据成为 RAG 和 Planner 的权威输入。元数据批准后，RAG 与 Experience 用 `asyncio.gather` 并发且独立降级；方案批准后，主图通过多目标 `Command.goto` fan-out 到所选 PPT/DOCX/HTML 节点，各分支写独立状态键，最后 fan-in 汇总。



### 实现流程



1. API 创建 Run；若请求是在恢复审批，先校验当前 checkpoint 中的 `interrupt_id`，防止旧审批卡恢复错误节点。
2. `AgentRuntime` 用 `thread_id` 读取 checkpoint；存在可恢复中断时输入 `Command(resume=...)`，否则构造新消息输入。
3. `START -> profile_memory_load_node -> conversation_entry_agent`。普通聊天结束；教学设计进入 intake；修改进入 revision router。
4. Intake 根据当前教学任务的有界 transcript 决定继续问一个问题，或提交完整 metadata；Profile 不能替用户补齐本次任务事实。
5. `metadata_review_interrupt_node` 批准后进入上下文准备；修正则回 intake。
6. RAG 与任务 Experience 并发准备，任一失败都可用空上下文继续。
7. Planner 生成结构化教学方案，进入 `teaching_plan_review_interrupt_node`。
8. 教师选择产物类型后并行执行专用 Artifact Agent，最后 fan-in；单支失败被结构化成 failed result，不吞掉其他成功分支。
9. 修改链优先使用入口 Agent 的 target hint；目标歧义时进入第三类审批卡，再只路由到选中的 revision 节点。



### 四个 interrupt 点与三类审批卡



- `interrupt_for_userinput`：普通自由文本需求澄清，不生成 approval 卡。

- `metadata_review_interrupt_node`：确认或修正教学要素。

- `teaching_plan_review_interrupt_node`：确认方案并选择产物类型。

- `artifact_revision_clarification_interrupt_node`：修改目标歧义时澄清。



因此，简历写“3 类审批”可以成立，但不能说“只有 3 个 interrupt”。更清晰的口述是“4 个可恢复中断点，其中 3 个形成审批卡”。



### 关键实现证据



- `backend/app/core/graph.py:595`：入口 Agent；`:713`：Intake Agent；`:804`、`:992`、`:1062`、`:1219`：四个 interrupt 节点；`:1271`：fan-in；`:1426-1483`：图装配与 checkpoint 编译。

- `backend/app/core/agent.py:1175-1249`：checkpoint 检测、过期审批校验和 `Command(resume)`；`:923-971`：三类 Artifact Agent。

- `backend/app/dependencies/db.py:95-121`：`AsyncPostgresSaver` 初始化。

- `backend/tests/test_main_graph_orchestration.py`、`backend/tests/test_approval_flow.py`：澄清、审批、选择性 fan-out/fan-in、旧 interrupt 拒绝。

- `docs/main-graph-orchestration.md`：当前拓扑；旧 `intent_router_node` / `metadata_structer_node` 已不再注册。



### 高频追问与回答



**Q1：为什么不用一个大 ReAct Agent？**  

A：流程里审批、并行副作用、版本切换和恢复顺序是硬约束。完全自治难保证这些边界。我把阶段与跳转放进 LangGraph，把阶段内开放式文件制作交给 Sub-Agent，既能确定性测试，又保留模型的生成能力。



**Q2：Checkpoint 保存的只是聊天记录吗？**  

A：不是。图以 `thread_id` 编译到 PostgreSQL checkpointer，保存节点位置和完整结构化 State。恢复时读取 pending interrupt，并用 `Command(resume=...)` 从对应节点继续。



**Q3：恢复为什么不会重复调用上一个模型或重复生成？**  

A：模型工作与 interrupt 分成独立节点，模型结果先进入 checkpoint，再进入等待；恢复执行 interrupt 返回后的跳转。不能把它泛化为所有外部副作用天然 exactly-once，因此产物层仍用 run/sub-run、状态和版本记录隔离。



**Q4：怎样防止用户点击旧审批卡？**  

A：前端提交 `interrupt_id`，后端与当前 checkpoint 的 interrupt 比较，不一致就拒绝。它解决同一 thread 已进入新审批阶段后旧 UI 仍可点击的问题。



**Q5：三种产物是否真的并行？**  

A：方案审批返回节点列表，同一 superstep fan-out，各节点写 `ppt_result`、`lesson_plan_result`、`game_result` 等独立键，再共同进入 fan-in。实际并发度仍受图执行器、连接池和模型服务限制。



**Q6：一个产物失败会怎样？**  

A：分支捕获异常并把对应 Artifact 标为 failed，fan-in 汇总 ready/failed；其他分支仍可交付。数据库或 checkpoint 等主基础设施故障仍可能终止整个 Run。



**Q7：为什么完整后才持久化 metadata？**  

A：避免半成品字段被误当成权威状态，污染 RAG 查询和方案生成；缺点是 UI 无法直接展示逐字段草稿。当前用“可见问题 + 完整 canonical snapshot”换取状态一致性。



**Q8：RAG 和 Experience 为什么并发、为什么 fail-open？**  

A：两者都是增强上下文且互不依赖，串行只增加延迟；可选增强失败不应阻止基础教学设计，所以独立捕获并降级为空。需要强事实依赖的场景则应改为 required/fail-closed。



**Q9：Sub-Agent 与普通函数节点有什么区别？**  

A：三类产物 runnable 都由 `create_agent` 构造，有专属 system prompt、Skill/Policy/Retry/Observation middleware 和多步工具执行；主图节点只是把状态适配给它，不是一次 LLM 调用换 prompt。



---



## 3. 第 2 条：双层长期记忆



> 设计用户画像 + 经验双层长期记忆机制，通过 Namespace 实现用户级隔离，并支持记忆检索、反思写入、冲突更新、确定性脱敏与可视化管理；8 个真实模型记忆场景全部通过验证。



### 应该怎样介绍



我没有把所有历史都塞回 Prompt，而是按生命周期拆成 Profile 与 Experience。Profile 保存教师身份、稳定偏好和长期约束，每次图启动只加载一次并有界注入；Experience 保存可复用的教学策略和工作流经验，只在教学规划或产物任务真正需要时语义检索。两类数据分别放在 `("users", user_id, "profile")` 和 `("users", user_id, "experiences")` namespace 中，认证用户 ID 不由客户端传入。



Experience 先用 pgvector 对 `title/summary/tags` 召回，再按标题精确命中、高置信语义命中、小模型 selector 的顺序最多选 3 条。选中结果做任务级 checkpoint 快照，规划、审批恢复和并行产物复用同一份记忆，只有学科、年级、主题等检索范围实质变化时刷新。



写入不阻塞主图：Run 终态事务只登记经过 allowlist、长度限制和规则脱敏的不可变 reflection snapshot；后台单 Worker 调用记忆模型产生 create/update/noop proposal。`MemoryService` 用用户级 advisory lock、版本号、人工修改时间、删除墓碑和 job idempotency 避免旧后台结果覆盖用户编辑、删除后复活和重复创建。



### 功能特点与实现



- 双层职责：Profile 小而稳定、每任务读取；Experience 可增长、按需召回，降低噪声和 token。

- 检索上限：默认候选 12、阈值 0.82、最终最多 3 条、上下文最多 6000 字符。

- 快照稳定性：scope key 对检索相关任务字段做 hash；同一任务跨恢复和 fan-out 不重复检索。

- 异步反思：主响应不等待反思模型；Worker 处理结构化 proposal。

- 一致性：自动更新必须满足 `base_version == guard.version`；人工修改晚于 snapshot 时自动 proposal 判 stale。

- 删除防复活：物理删 Store 的同时保留 mutation guard 墓碑。

- 幂等：reflection job 有组合唯一约束；自动 create 的 memory id 由 job id 确定；Store/guard 记录最后应用 job。

- 隐私与注入防护：程序规则处理手机号、邮箱、证件、校名、经济背景、token、URL、对象键、宿主路径；记忆 HTML escape 后作为“不可信背景”注入，当前用户指令优先。

- 用户治理：前端按 Profile/Experience 查看、搜索、编辑、删除，人工操作会推进 guard 版本。

- 降级：Experience Store、向量或 selector 异常默认返回空 bundle，不阻断主流程，并记录 degraded 原因。



### 8/8 的准确口径



已晋升 mixed baseline 中，三个记忆分类均标为 `model-eval`：`memory_retrieval` 3/3、`memory_update` 1/1、`memory_write` 4/4，共 8/8、0 ERROR，使用的记忆模型是 `qwen3.7-flash-2026-07-15`。场景覆盖 Profile 加载、相关/无关 Experience、普通聊天不写、隐私不落库、完整画像抽取、冲突更新、多语言边界。



这只是一次固定小数据集的 8/8，不等价于“长期记忆准确率长期 100%”；整个 24 例报告是 23/24，且 baseline 记录了 dirty worktree。



### 关键实现证据



- `backend/app/core/memory.py:186-196`：namespace；`:307-383`：Store CRUD；`:665-790`：反思 prompt/proposal。

- `backend/app/core/memory_retrieval.py:341-563`：语义候选、三级选择、白名单校验与降级。

- `backend/app/core/graph.py:843-989`：Profile 与任务 Experience；`:1386-1424`：并发准备。

- `backend/app/services/memory_reflection_service.py`、`backend/app/core/memory_worker.py`：snapshot 登记和后台 Worker。

- `backend/app/services/memory_service.py`、`backend/app/models/memory_reflection.py`：锁、版本、墓碑、幂等模型。

- `backend/app/api/memory.py`、`frontend/src/layout/components/Sidebar.vue`：用户可视化 CRUD。

- `docs/benchmarks/baselines/stage1-model-eval-2026-07-30/summary.json`：8 个 memory model-eval 用例均通过。



### 高频追问与回答



**Q1：为什么不放进一个向量库？**  

A：Profile 高频且几乎总相关，检索可能漏掉关键偏好；Experience 稀疏相关且不断增长，全量常驻会污染上下文。分层后前者有界加载，后者按需召回。



**Q2：Namespace 就能防越权吗？**  

A：Namespace 只是存储键，真正边界是 user id 来自 JWT 认证依赖，API schema 不接收客户端 user id，所有查询再带用户条件。测试也覆盖伪造 user id 不会写入其他 namespace。



**Q3：为什么还需要小模型 selector？**  

A：精确标题和高置信向量结果可确定性直出；低置信难例才把截断候选摘要交给小模型 rerank。返回 id 与候选白名单求交后再回表，避免模型任意访问记忆。



**Q4：为什么反思移出主图？**  

A：同步反思增加 SSE 尾延迟，也会让记忆模型失败污染主任务。现在终态事务登记 job，用户响应不等待。当前边界是运行中 Worker 任务在进程崩溃时标记失败，没有 lease 自动接管。



**Q5：旧后台结果怎样避免覆盖用户新编辑？**  

A：人工变更先获取用户级 advisory lock，推进 guard version 并记录时间；自动 proposal 携带抽取时的 base version 和 captured_at，任一不匹配就 stale。



**Q6：删除后会不会被旧任务复活？**  

A：删除会递增版本和 deletion generation、设置 tombstone，再删 Store；旧 proposal 命中 tombstone 后不能应用。



**Q7：怎样保证任务幂等？**  

A：登记层有组合唯一约束，create id 由 job id 哈希得到，guard 与 Store 都记录 last applied job。即使 Store 写成功但 job ack 前崩溃，重放仍能识别已应用。



**Q8：“确定性脱敏”是不是能识别所有 PII？**  

A：不是。“确定性”表示已定义的模式必经同样的程序转换，而不是世界上所有隐私都能识别。因此还需要最小化、字段 allowlist、用户删除和持续扩充规则，不能只依赖 Prompt。



**Q9：记忆会不会发生 Prompt Injection？**  

A：记忆永远作为不可信数据处理，escape 后包在专用标签内，system prompt 明确它不是指令，当前显式用户要求优先；Experience 搜索工具也不能传 user id 或写参数。



**Q10：为什么要做任务级快照？**  

A：Planner、审批恢复和三个产物 Agent 必须基于同一组经验，否则每次召回会因索引变化或模型选择不同产生漂移。只有检索语义范围实质改变才刷新。



---



## 4. 第 3 条：上下文压缩



> 针对长程 Agent 设计上下文压缩机制，保留结构化任务状态与近期对话；在 30/50/100 轮合成长对话实验中，累计 Prompt Token 量净降低 21.2%–70.6%。



### 应该怎样介绍



系统状态同时包含不断增长的 `messages` 和教学元数据、RAG、方案、产物、revision 等结构化字段。我只压缩消息历史，结构化字段保持权威且不由摘要模型改写；压缩时再从这些字段构造有长度上限的 structured preface，与旧对话一同送给专用摘要模型。新状态用一个带标记的 `SystemMessage` 替换旧历史，并原样保留最近 N 个以 HumanMessage 划分的完整轮次。



压缩在完整对话轮结束后检查，低于阈值、等待审批、存在可恢复 interrupt、消息 ID 缺失或旧消息太少时跳过。模型调用或 checkpoint 更新失败则 fail-open：不返回 State update，保留原消息，主流程继续。



### 算法与工程特点



- token 估算优先调用模型 tokenizer；不可用时回退到字符数加角色开销除以 4。

- 默认关闭；默认软阈值 24k、保留近期 6 轮、summary 预算 3k、structured preface 6k 字符。

- 近期轮按 HumanMessage 边界保留，而不是简单保留 `2N` 条，因此其中的 tool/system 消息也不会被拆散。

- preface 只抽取选定权威字段的有限快照，不是完整 State 序列化。

- 下次压缩会把旧 compressed message 纳入旧历史并替换为一个新摘要，避免摘要消息堆叠。

- 删除旧消息依赖 LangGraph `RemoveMessage(id)`；缺 ID 时宁可跳过。

- 观测只记录 checked/skipped/started/completed/failed、计数、大小、耗时和原因，不记录消息或摘要正文。



### 21.2%–70.6% 怎样得到



正式 A/B 使用固定合成八年级数学备课对话。A 关闭压缩；B 有 3 条独立 100 轮线程，在 30/50/100 轮取嵌套快照；主 Agent 回复是确定性 fixture，只有摘要调用真实 `qwen3.7-flash-2026-07-15`。阈值 6000、保留 6 轮，共 18 次真实摘要，18/18 成功。



净削减公式为：



```text

1 - (B 组累计主 Prompt 估算 + B 组压缩输入/输出估算开销)

​    / A 组累计主 Prompt 估算

```



| 轮数 | A 累计估算 | B 主链路估算 | 计入压缩开销后的净削减 |

| ---: | ---: | ---: | ---: |

| 30 | 124,518 | 92,357 | 21.17% |

| 50 | 347,748 | 180,348 | 43.18% |

| 100 | 1,396,699 | 376,850 | 70.55% |



简历的 21.2%–70.6% 是一位小数四舍五入，数字准确。但必须称“固定合成实验中的估算 token”，不是供应商账单或生产成本。摘要延迟 p50/p95 为 21.28s/25.40s，近期 6 轮与权威非 messages 状态保持 100%，早期事实在 50/100 轮为 91.67%，说明压缩仍有信息损失。



### 关键实现证据



- `backend/app/core/state.py:29-65`：messages 与业务状态分离。

- `backend/app/core/context_compression.py:111-180`：估算、阈值、轮边界；`:183-334`：preface、摘要和替换；`:337-463`：跳过、失败回退和观测。

- `backend/app/core/agent.py:1302-1399`：runtime 更新；`:2404-2441`：审批完成后的接入时机。

- `backend/tests/benchmarks/context_compression_ab.py`：直接调用生产压缩入口的 A/B 脚本。

- `docs/benchmarks/baselines/context-compression-ab-2026-07-31/report.md`：正式数字和限制。



### 高频追问与回答



**Q1：为什么不直接截断最老消息？**  

A：截断会丢早期目标、约束和未决问题。摘要旧历史、重建结构化 preface、原样保留近期轮，能同时照顾长期事实和短期语用。



**Q2：为什么只压缩 messages？**  

A：元数据、方案、产物和 revision 是路由与恢复依赖的权威状态，让模型重写会引入漂移；messages 增长最快，所以只治理它。



**Q3：触发阈值如何确定？**  

A：当前是可配置软阈值，完整轮结束后检查。生产可在模型有效窗口的约 60%–75% 灰度设定，并结合延迟、失败率和真实 provider usage 调整，而不是等到硬上限才处理。



**Q4：为什么审批期间不压缩？**  

A：interrupt 恢复依赖 checkpoint 中的消息和 next node 语义。等待期间改写消息会增加恢复风险，因此恢复并完成一轮后再压缩。



**Q5：压缩失败会怎样？**  

A：模型或 checkpoint 更新异常返回 failed 且 `update=None`，原消息不变，SSE 显示压缩失败但主 Run 继续；这是一项成本优化，不能成为主功能单点。



**Q6：多次摘要如何避免漂移和膨胀？**  

A：每次把旧摘要也纳入待压缩区，最终只留下一个新 compressed message；同时用未被改写的结构化字段重新校准。实验中早期事实只有 91.67%，所以不能声称无损。



**Q7：这个数字是实际 token/成本吗？**  

A：不是账单 token。由于 Qwen 没有本地 tokenizer，统一走生产 `chars/4` 回退；A/B 口径一致、可复现，但只能称估算 token 削减。



**Q8：30/50/100 是 9 条独立实验吗？**  

A：不是。control 是确定性一条；treatment 是 3 条各跑 100 轮，并在三个轮数取快照。应准确描述为嵌套观察点。



**Q9：最大问题和下一步是什么？**  

A：真实摘要 p95 约 25.4 秒，且历史事实并非 100%。下一步会用更小更快模型、提前或异步压缩、结构化事实槽摘要，并用脱敏真实会话和 provider usage 校准。



---



## 5. 第 4 条：三类 Artifact、Revision、SSE 与 MinIO



> 构建 PPTX、DOCX、HTML 三类 Artifact 生成与 Revision 差量修改链路，统一接入 SSE 与 MinIO；30 次跨学科真实模型实验中 29 次产物可用（96.7%）。



### 应该怎样介绍



教师批准方案后可选择一种或多种产物，主图把同一份元数据、方案、RAG 和记忆快照扇出给三个专用 Agent。每个 Agent 必须通过 Workspace 工具生成真实文件到 `AGENT_OUTPUT_DIR`，分别加载 `ppt-generator`、`docx`、`html-interactive` skill；最后 fan-in 汇总 ready/failed，因此某一格式失败时其他格式仍可交付。



产物开始时先写 `running` ArtifactFile 并发送 SSE，完成后经 `StorageService` 上传 Local/MinIO 并变为 ready，异常则记 failed；Agent 内部消息、工具调用与状态通过 `artifact_trace` 展示。Redis Stream 为事件分配单调 sequence，前端断线后用 cursor 续传，终态再拉 Artifact API 对账。



Revision 不覆盖旧文件：先确定修改目标，必要时 HITL 澄清；从 StorageService 物化当前 ready 版本到 Workspace，Office 文件解包 OOXML 并生成摘要，HTML 读取源文本，Agent 尽量做 targeted edit。新记录通过 `parent_artifact_id`、`root_artifact_id`、`revision_number` 形成版本链，只有新文件上传成功才在事务中切换 `is_current`；失败时旧版仍 current。存储的是完整新文件，不是二进制 delta。



### 功能特点与实现



- 三种格式各有独立 prompt、skill、run id 和结果键，共用 AgentRuntime middleware 与 Workspace。

- 多目标 `Command.goto` 做选择性 fan-out，六个生成/修改节点统一进入 fan-in。

- StorageService 以 `storage_backend + storage_key` 定位对象，需要本地文件时临时物化，业务不直接依赖 MinIO 路径。

- `artifact` 事件表达 running/ready/failed，`artifact_trace` 表达内部执行轨迹。

- PPTX/DOCX 通过 OnlyOffice 预览/编辑；HTML 通过 iframe 预览。

- 当前前端只展示 current 产物，没有版本树/回滚 UI；OnlyOffice 人工保存会覆盖同一记录，不自动创建 revision。



### 96.7% 的准确口径



正式样本是数学、语文、物理、化学、信息技术 5 个固定合成场景 × 2 次重复 × 3 种产物 = 30 个产物尝试。结果 PPT 10/10、DOCX 9/10、HTML 10/10，唯一失败是 DOCX 达到 600 秒外层超时，因此 29/30=96.67%。一个“产物尝试”会包含多次 LLM/tool 调用，本报告累计 488 次 LLM call，不能说成“30 次模型 API 调用”。



“可用”定义为：ready、通过 ZIP/XML/OOXML schema 或 HTML 静态结构/JS 检查，并达到必备术语覆盖和确定性内容结构 rubric。实验当时没有 OnlyOffice/LibreOffice 视觉渲染与溢出检查，没有浏览器 E2E，也没有教师盲评，因此不等价于“可直接上课的教学质量”。



### 关键实现证据



- `backend/app/core/agent.py:867-971`：三个 Artifact Agent；`:1739-2155`：生成/修改 Job 和 Workspace 准备。

- `backend/app/core/graph.py:1062-1091`：选择性 fan-out；`:1271-1297`：fan-in；`:1098-1253`：revision 路由/澄清。

- `backend/app/models/file.py:106-174`、`backend/app/services/artifact_service.py:276-470`：版本链与 current 切换。

- `backend/app/core/storage.py:196-437`：MinIO、预签名与临时物化。

- `backend/app/core/chat_run_events.py`、`backend/app/api/chat.py:218-322`：可续传事件。

- `frontend/src/components/FilePreviewPanel/index.vue`、`frontend/src/components/ContextPanel/index.vue`：OnlyOffice/HTML 预览。

- `docs/benchmarks/baselines/artifact-generation-2026-08-03/report.md`：29/30 基线。



### 高频追问与回答



**Q1：为什么拆三个 Agent？**  

A：三种格式依赖、skill 和验证逻辑不同，拆分后权限与上下文更聚焦，也能并行降低墙钟时间；独立错误边界允许部分成功。



**Q2：你说差量修改，数据库存 diff 吗？**  

A：不存。差量体现在基于指定源版本做 targeted edit，持久化仍是完整新文件。这样预览、下载和回退简单，代价是存储更多，可再通过对象去重或生命周期策略优化。



**Q3：新 revision 失败会覆盖旧版吗？**  

A：不会。新记录创建时不是 current，只有上传成功、状态 ready 后才事务切换；failed revision 不影响旧 current。进一步可加唯一部分索引和行锁处理同类型并发修改。



**Q4：parent、root、revision number 为什么都需要？**  

A：parent 表示直接来源，root 快速聚合同一家族，revision number 便于排序和展示，is_current 优化热查询；分别解决谱系、分组、顺序和当前态。



**Q5：断线为什么不丢产物状态？**  

A：后台 Run 不依赖 SSE 连接；事件先写 Redis Stream，客户端保存 sequence，重连回放并去重；最终状态还在 PostgreSQL，结束后通过 REST 对账。



**Q6：MinIO 下为什么不能直接 `Path(storage_path)`？**  

A：对象存储没有稳定本地路径。业务只持有 storage key，通过 StorageService 读写；Office 解包等必须要路径时用 context manager 临时物化并清理。



**Q7：OnlyOffice 编辑是否创建新版本？**  

A：目前 callback 写回同一 Artifact 记录，不创建 revision；自然语言 Agent 修改才创建新版本。这是现有边界，后续应让人工编辑也进入版本链。



**Q8：96.7% 是否代表教师可直接使用？**  

A：不能直接等同。它表示自动化技术与确定性内容结构门禁下的可用率，不包含审美、投影溢出、完整交互和教师教学质量评价。



**Q9：为什么不是 100%，如何处理长尾？**  

A：唯一失败是 DOCX 600 秒超时，分母保留而非重跑删除。下一步应做阶段级预算、最大工具轮次、早停、可恢复重试，而不是无限延长超时。



**Q10：HTML 预览有什么风险？**  

A：当前 iframe 缺少严格 sandbox，token 还可能进入 query；生产应使用独立预览域、CSP、最小 sandbox 权限和短时一次性凭据，并限制出站网络。



---



## 6. 第 5 条：受控 Agent Harness 与 Daytona 沙箱



> 建设受控 Agent Harness，通过 Policy Middleware 管理 Skill/Tool 权限，并实现路径穿越防护、执行超时、输出截断、失败重试与依赖安装约束；抽象本地 Workspace 与 Daytona 云沙箱双执行后端，实现模型生成代码与宿主环境隔离。



### 应该怎样介绍



这套 Harness 的目标不是“让 Agent 能运行代码”，而是让它只能在明确授权、可限制、可观测的边界内运行。模型初始只看到 Skill 摘要，调用 `load_skill` 后 Skill 才进入 `active_skills`；Policy Middleware 在每次敏感工具调用前检查该 Skill 的 `allowed-tools`。当前门禁覆盖 5 个 Workspace 工具和 Experience 搜索，是能力白名单，不是通用用户 RBAC。



Workspace 统一暴露 list/read/write/replace/run 五个接口。上层不感知执行后端：Local 在受控 cwd 中启动 Python/Node 子进程；Daytona 创建默认断网的独立 sandbox，上传 Workspace、远程执行、下载输出并清理。两者返回统一 `WorkspaceExecutionResult`。



### 防护与实现边界



- 路径：拒绝绝对路径，`resolve()` 后用 `relative_to(workspace_root)` 验证没有越界。

- 权限：active Skill 必须显式声明 Tool；这是执行前强制门禁，不只靠 Prompt。

- shell 旁路：拦截 Python/Node/npm/pip 等常见入口，要求走受控 Workspace 工具。

- 超时：Local 默认 30 秒；Daytona 默认远程执行 120 秒并统一映射 timeout 结果。

- 输出：stdout/stderr 和文本读取最多 12,000 字符、200 行。

- 依赖：入口源码规则拦截常见 pip/npm 安装；依赖应预装在宿主或 snapshot/image。

- 重试：`ToolRetryMiddleware(max_retries=3)` 处理抛异常的 Tool 调用；权限拒绝和非零退出不会被无意义重试。

- Daytona：snapshot/image 二选一，默认 `network_block_all=True`，结果下载到本地 output 后继续走 Artifact/Storage 链。

- 可观测：记录 backend、language、entrypoint、exit/timed_out、输出大小、错误类别和耗时，不记录输出正文。



必须承认：Local 没有 OS 级文件、网络、进程、CPU/内存隔离，正则也可能被混淆或间接执行绕过；生产不可信代码的强边界来自 Daytona/容器。`run_skill_script` 执行的是仓库内受信 Skill 脚本并在宿主运行，其安全前提是 Skill 发布物可信。



### 关键实现证据



- `backend/app/core/agent.py:163-171`：门禁工具和 shell 规则；`:466`：SkillPrompt；`:509`：Policy；`:890-902`：Retry 装配。

- `backend/app/core/skills.py:256-310`：`allowed-tools` 与资源路径；`:427-525`：激活 Skill。

- `backend/app/core/workspace.py:323-345`：路径防护；`:390-488`：Local；`:491-794`：Daytona；`:925-1020`：校验与观测。

- `backend/app/config.py:553-618`：双后端和 Daytona 默认策略。

- `backend/tests/test_workspace_manager.py`、`backend/tests/test_skill_aware_agent.py`、`backend/tests/test_skill_registry.py`：目标测试 26 个通过。

- `openspec/specs/agent-sandbox-execution/spec.md`：安全与后端契约。



### 高频追问与回答



**Q1：为什么不能只靠 System Prompt？**  

A：Prompt 是概率约束，可能被提示注入或复杂上下文绕开；Policy 在 Tool handler 前执行，即使模型发出违规 call，也只会得到权限错误，不产生副作用。



**Q2：Skill 与权限怎样关联？**  

A：`SKILL.md` frontmatter 声明 `allowed-tools`；加载后写入 active state；每次敏感调用重新计算 active skills 是否至少有一个允许该 Tool。



**Q3：为什么不为每个 Skill 创建独立 Agent？**  

A：动态激活允许同一长任务组合多个 Skill，并减少初始 Prompt；代价是必须把激活状态显式化并在每次 Tool 调用前复核。



**Q4：路径穿越为何不能只检查 `..`？**  

A：字符串检查处理不了规范化、混合层级和符号链接。当前先拒绝绝对路径，再 resolve 最终路径并检查它仍属于 Workspace；但这只保护工具 API，Local 生成代码本身仍可尝试访问宿主路径。



**Q5：Local 算沙箱吗？**  

A：严格来说不是强沙箱，只是受控执行器：入口、cwd、环境变量、时间和输出受限，但进程仍有业务用户的宿主权限。生产应选择 Daytona 或同级容器/微虚机。



**Q6：为什么 Daytona 故障不自动回退 Local？**  

A：选择 Daytona 代表安全策略；静默回退会把“隔离服务故障”变成“宿主执行”，属于危险的 fail-open。当前明确失败更安全。



**Q7：怎样阻止运行时安装依赖？**  

A：Prompt、shell 路由拦截、入口源码扫描三层降低风险；真正可靠的做法是预制 snapshot/image 并默认断网。正则不是系统调用级防护，不能过度承诺。



**Q8：Daytona 中的产物如何回到系统？**  

A：执行前上传 Workspace，代码按协议写远端 `AGENT_OUTPUT_DIR`；执行后列举并下载 outputs，再由 ArtifactService 统一进入 StorageService/MinIO。



**Q9：Skill 脚本为什么在宿主执行？**  

A：它属于仓库随版本发布的受信代码，与模型动态生成代码信任等级不同；路径仍限制在 Skill 的 `scripts/`。若未来允许用户上传 Skill，脚本也应迁入沙箱并增加签名审核。



**Q10：当前权限模型的不足？**  

A：粒度只是 Tool 名称，无法表达只读目录、扩展名、次数或用户/组织策略；下一步应加入参数级 Policy Decision、资源配额、红队用例和独立审计。



---



## 7. 第 6 条：可观测性与评估闭环



> 建立覆盖 LLM、Tool、RAG、Workspace 的可观测与评估体系，以统一 RunContext 串联结构化日志、OpenTelemetry Trace 与 Prometheus Metrics；沉淀 24 个评估用例，真实模型基线通过率 95.8%。



### 应该怎样介绍



这项工作的重点不是接入某个监控 SDK，而是让一次跨 API、LangGraph、Sub-Agent、LLM、Tool、RAG、Workspace 的长程运行共享同一事件模型。不可变 `RunContext` 携带 `run_id/thread_id/plan_id/user_id/agent_name`，通过 RunnableConfig 显式传播；子 Agent 用 `with_agent()` 派生上下文。



业务侧统一使用 `log_observation`、`trace_span`、`record_metric` 和 `observe_llm_call`。LLM 记录模型、消息数量、输入输出规模、token 与耗时；Tool 只记录工具名和参数键；RAG 记录 query size 和结果数；Workspace 记录语言、后端、退出码、超时和输出大小。所有 sink 可组合且运行期 fail-open，监控故障不会拖垮用户任务。



Trace 和日志承担逐请求关联；Prometheus 只用 agent/model/status/error 等低基数枚举，明确禁止 run/user/thread、文件名、对象 key、URL 等进入 label。隐私采用三层防线：源头不采正文、统一递归脱敏、公开 benchmark 只从 allowlist 重建聚合证据。



评估侧，YAML 用例先做严格 schema、category、assertion 和字段合同校验，再按分类执行 evaluator，产出 Schema 2.0 报告。回归门禁要求六分类齐全、0 ERROR、各分类达到阈值；只有通过门禁的报告才能晋升到 `docs/benchmarks/baselines/`。



### 95.8% 的准确口径



基线共有 24 例，23 PASSED、1 FAILED、0 ERROR，`pass_rate=95.83%`，`avg_score=0.942`。两者不能混用。20 个 model-eval 覆盖意图、抽取、记忆；4 个上下文压缩例是 deterministic，因此报告标为 mixed。唯一失败是一个歧义教学要素抽取用例，路由正确但漏掉明确出现的“数学”，失败被保留而没有调低标准。



还要区分两件事：LLM/Tool/RAG/Workspace 是统一可观测覆盖面；24 个评估用例本身覆盖意图、抽取、记忆和压缩，并没有直接评估 Tool/RAG/Workspace 的质量。



### 关键实现证据



- `backend/app/core/observability.py:70-154`：RunContext、Event 与 Sink；`:614-825`：span/LLM 观测；`:1078-1230`：低基数治理。

- `backend/app/core/agent.py:639-770`：LLM/Tool middleware。

- `backend/app/core/graph.py:329-360`、`:1316-1353`：节点/RAG span。

- `backend/app/core/workspace.py:930-1006`：Workspace 观测。

- `backend/app/core/observability_bootstrap.py`：可选 OTEL/Prometheus 初始化。

- `backend/tests/evals/suite_validation.py`、`runners/eval_runner.py`、`check_regression.py`：严格校验、执行和 fail-closed 门禁。

- `docs/benchmarks/baselines/stage1-model-eval-2026-07-30/report.md`：23/24 基线。



### 高频追问与回答



**Q1：为什么一个 request id 不够？**  

A：Run 会跨断线重连和审批恢复，thread 聚合同一会话，plan 关联教学任务，agent 区分并行 Sub-Agent；单一 HTTP request id 覆盖不了这些生命周期。



**Q2：为什么通过 RunnableConfig 传播，不用全局变量？**  

A：显式配置更适合 checkpoint 恢复、测试注入和并行分支，也不会被线程/协程局部状态隐式污染。



**Q3：日志、Trace、Metrics 各自解决什么？**  

A：日志回答发生了什么，Trace 还原单次 run 的跨组件时序，Metrics 观察整体调用量、错误率和延迟趋势。高基数关联 ID 只能进日志/Trace。



**Q4：为什么 Prometheus 不能放 run_id？**  

A：每个唯一 label 组合都会形成时间序列，run/user/file/url 几乎无界，会造成 TSDB 内存、索引和查询爆炸，也可能泄露身份。



**Q5：怎样保证不记录 prompt 或 RAG chunk？**  

A：埋点 API 从源头只采 size/count/key names；fields 再经过敏感键和内容正则脱敏；公开基线最后由独立 allowlist 重建。最重要的是不采，而不是事后清洗。



**Q6：监控系统故障会怎样？**  

A：Composite sink 逐出口隔离异常，emit 还有兜底，运行期 fail-open；但若部署显式开启 OTEL 却缺 endpoint，启动配置应 fail-fast。



**Q7：FAILED 与 ERROR 有什么区别？**  

A：FAILED 是程序完成但质量断言未过；ERROR 是运行、evaluator 或 judge 出错，结果不可信。门禁强制 ERROR=0，不能把它混入失败后稀释统计。



**Q8：95.8% 为什么不是 94.2%？**  

A：95.83% 是 23/24 的用例通过率；94.2% 是各例部分得分平均值。简历使用 pass rate，不能拿 avg score 替代。



**Q9：为什么按分类门禁？**  

A：总体均值会让大量简单用例掩盖小分类退化。门禁要求六分类都存在、0 ERROR、分别达到阈值，才能 fail-closed。



**Q10：如何改进评估可信度？**  

A：扩大薄弱分类，尤其只有 1 例的 memory update；真实模型做多次重复和置信区间；为 Tool 选择、RAG recall/faithfulness、Workspace 安全建立独立质量评估，并在 clean commit 上重跑。



---



## 8. 第 7 条：认证 SSE 分层压测与故障归因



> 对认证 SSE 链路进行分层性能测试，累计完成约 2.6 万次请求；Mock LLM 场景零失败、完整请求 p95 ≤ 590ms，真实模型 8 路并发成功率 99.1%，通过 Trace 将主要失败定位至上游流式响应超时。



### 应该怎样介绍



我为认证后的非 RAG 普通聊天建立分层 SSE 基线。请求完整经过 JWT、FastAPI、LangGraph/Agent 与 SSE 序列化，只把上游模型分别替换成确定性本地 Mock 或真实 provider。Mock 用来测本地认证、协议和编排开销；Live 用来测真实 TTFT 和完整流时延。矩阵是 1/2/4/8 并发 × 每档 3 个独立 5 分钟窗口 × 两种模式。



成功不能只看 HTTP 200：压测器逐帧解析 SSE，必须同时看到 metadata、至少一个 token、done，且不能出现 error。它分别上报 TTFT 与完整流耗时；资源采样器每秒记录 CPU、内存、线程和句柄；聚合器保留每个窗口的 p50/p95，再报告最坏窗口，而不是从已聚合分位数伪造全局 p95。



### 数字与结论



- Mock：24,457 请求，0 失败；1/2/4/8 并发的最坏完整 p95 分别 230/240/320/590ms，8 并发 TTFT p95 最坏 240ms。

- Live：1,671 请求；8 并发 788 请求、7 失败，`781/788=99.1117%`，即 99.1%。

- 合计：24,457 + 1,671 = 26,128，约 2.6 万请求，不是 2.6 万用户。

- Live 8 并发失败阶段 CPU p95 仅 1.8%，而 Mock 以更高吞吐运行仍零失败；已捕获的 3 条明确错误为 120 秒没有收到模型 streaming chunk。结合 Trace/错误事件可把主要故障域收敛到上游流式稳定性。



必须主动说明：Live 正式 gate 是 FAIL 且没有晋升 baseline；7 个失败中只有 3 个在脱敏 summary 中保留了明确的无 chunk 分类。实验针对旧兼容 `/api/chat/stream`，不是当前 `POST /chat/runs + GET events` 的 Redis 可回放链路；也不覆盖 RAG、附件或产物生成，不能包装成生产 SLA。



### 当前持久 Run SSE 架构（与上述 benchmark 分开讲）



新版链路先在 PostgreSQL 创建 Run，由进程内 `ChatRunManager` 后台执行；事件通过 Lua 原子递增 sequence 并写 Redis Stream，token 同时追加输出快照。订阅端支持 `after_sequence` / `Last-Event-ID`，先回放再阻塞等待；浏览器断开只结束订阅，不取消 Run。阻塞 reader pool 与 command pool 分离，避免大量 `XREAD BLOCK` 占满普通命令连接。Redis 不可用时 readiness 和接口显式失败，不做静默内存回退。



当前仍是单进程、单 worker MVP；进程重启会把遗留 running Run 标 failed，而不是跨进程自动接管。



### 关键实现证据



- `backend/tests/benchmarks/sse_load.py:147-262`：认证、逐帧协议校验、TTFT/full 指标。

- `backend/tests/benchmarks/sse_protocol.py`：解析、分位与脱敏错误分类。

- `backend/tests/benchmarks/run_sse_matrix.ps1`、`resource_sampler.ps1`：正式矩阵与资源采样。

- `docs/benchmarks/runs/sse-chat-load-formal-2026-08-07/report.md`：26,128 请求与 FAIL gate。

- `backend/app/api/chat.py:63-322`：持久 Run 创建/订阅；`:325-430`：被压测的兼容接口。

- `backend/app/core/chat_run_events.py`：Redis 原子序列、双连接池、回放与 done。

- `backend/app/core/chat_runs.py`：后台调度、事件发布与终态。



### 高频追问与回答



**Q1：为什么要拆 Mock 和真实模型？**  

A：只跑 Live 无法判断慢在本地协议还是 provider；只跑 Mock 又不代表用户体验。两者保留同一服务路径，只替换模型时间，差值用于归因而不是质量对比。



**Q2：为什么 HTTP 200 不算成功？**  

A：SSE 响应头发出后仍可能 error、断流或缺 done；所以必须检查事件协议完整性，避免“200 假成功”。



**Q3：TTFT 与完整流耗时各说明什么？**  

A：TTFT 是用户多久看到第一段内容；完整耗时决定总体验和连接占用。Live 8 并发 TTFT p95 最坏 2.9s，但某窗口 full p95 到 135s，说明尾部问题不等同于首 token 普遍变慢。



**Q4：为什么不把三个窗口合并算 p95？**  

A：现有输入是窗口级频次/分位摘要，没有全部原始延迟样本。保留每窗 p95 并报最大值是诚实口径，从分位数再次聚合会产生伪统计。



**Q5：怎样判断不是本机 CPU 瓶颈？**  

A：Live 失败时 CPU p95 只有 1.8%；Mock 更高吞吐时 CPU p95 约 6.45% 仍零失败；再结合 120 秒无上游 chunk 的明确错误，CPU 饱和与现象不匹配。但不能据此永久排除所有本地连接池因素。



**Q6：99.1% 是 SLA 吗？**  

A：不是。它是单机 Windows、固定非 RAG prompt、3 个五分钟窗口下的 `781/788`，而且正式门禁失败，只是实验结果。



**Q7：登录耗时为什么不混入聊天指标？**  

A：每个虚拟用户启动时只登录一次，聊天会重复；混合统计会随窗口请求量改变权重。登录仍真实执行，失败会阻止用户继续，只以 `[setup]` 单独上报。



**Q8：断线续传怎样保证顺序？**  

A：Lua 一次完成递增 sequence、XADD、token snapshot 和 TTL；客户端只消费 cursor 之后的事件并按 sequence 去重。语义更接近可重放的 at-least-once，不应宣称端到端 exactly-once。



**Q9：为什么 Redis 要分两个连接池？**  

A：`XREAD BLOCK` 长时间占用连接，若与 append/readiness 共池，订阅增多会饿死短命令；reader pool 与 command pool 分离能隔离容量。



**Q10：下一步怎样压测新版 Run 链路？**  

A：分别压创建 Run、首次订阅和带游标重连回放，记录 Redis pool saturation、replay lag、TTFT、协议完整率和 provider 错误；再扩大并发并加入 RAG/附件场景，同时引入上游并发阈值、超时预算与熔断策略。



---



## 9. 可主动讲的项目局限与改进顺序



1. **Durable Run**：当前后台任务仍在 FastAPI 进程内且按单 worker 设计；下一步拆独立 Worker，用 PostgreSQL claim + lease/heartbeat/fencing token 和 artifact execution key 实现多实例接管与幂等。
2. **Sandbox**：生产配置应禁止 Local；为 Daytona 增加 CPU/RAM/disk/process 配额，并把未来用户 Skill 脚本也移入隔离环境。
3. **Artifact 安全与版本**：HTML 独立预览域 + sandbox/CSP；OnlyOffice 开启 JWT；人工编辑也创建 revision；补版本树与回滚 UI。
4. **Artifact 质量**：加入 LibreOffice/OnlyOffice 渲染截图、溢出检测、Playwright 交互 E2E 和教师盲评，将 generation 与 revision 分开建基线。
5. **Memory**：扩大冲突、过期偏好和跨学科迁移样本；在 clean commit 上多次重复并报告置信区间。
6. **Compression**：用 provider usage 校准 token，使用更快摘要模型或预压缩，改进早期事实槽位保留。
7. **Evaluation**：为 Tool 选择、RAG recall/faithfulness、Workspace 安全单独建立质量评估，不把“可观测覆盖”与“24 例评估覆盖”混为一谈。



## 10. 本次核查说明



- 只新增本面试准备文档，没有修改现有业务代码或简历。

- 对当前实现执行了定向测试：



```text

95 passed in 9.92s

```



- 测试范围包括主图编排、审批、长期记忆、上下文压缩、Artifact 流、Workspace、可观测与聊天负载统计。首次运行被本机自动加载的 `pytest-qt` 的 Qt DLL 问题干扰；显式禁用无关插件自动加载并加载 `pytest_asyncio` 后通过。

- 所有 benchmark 都应按各自报告的条件和限制使用；不能将个人项目的固定评估或压测描述成生产用户流量或 SLA。
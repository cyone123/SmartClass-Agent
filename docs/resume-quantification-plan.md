# SmartClass 简历量化数据与工程结果补充方案

日期：2026-07-26
目标：解决简历项目经历"缺少数据支撑和工程结果证明"的问题——不是重写简历文案，而是**让项目真的产出可复现、可解释、面试时经得起追问的数字**，再把数字写回简历。

---

## 1. 核心判断

先说结论：**这个项目缺的不是测量基础设施，而是"跑出数字并沉淀下来"这最后一步。**

现状盘点（都是已存在的事实）：

| 已有基础设施 | 位置 | 能产出什么数字 |
| --- | --- | --- |
| 评估 harness + 24 个评估用例（intent 5 / extraction 7 / memory 8 / context_compression 4） | `backend/tests/evals/` | 各维度通过率、平均分、回归对比 |
| 评估运行器与回归检查 | `evals/runners/eval_runner.py`、`evals/check_regression.py` | suite 级 passed/failed/avg_score 报告（JSON） |
| 全链路 `duration_ms` 埋点（LLM 调用、工具、RAG、产物生成、存储、workspace 执行、压缩） | `observability.py`、`agent.py`、`graph.py` 等 | 各环节耗时分布 p50/p95 |
| Prometheus + OTel + Grafana 接入 | `docs/observability/` | 请求速率、LLM/工具失败率、token 用量 |
| 上下文压缩事件（checked/skipped/started/completed/failed） | `context_compression.py` | 压缩率、token 削减量、压缩耗时 |
| ~20 个后端功能测试文件 | `backend/tests/` | 测试数量、覆盖率 |
| Docker Compose 全栈（backend/frontend/PG/MinIO/OnlyOffice/Prometheus/Grafana） | `docs/deployment/docker.md` | 一键部署、服务数量 |

所以补数字的路线是：**用现有设施设计一批"可复现实验"，把结果沉淀成报告文件（进仓库），简历引用报告里的数字。** 面试官追问时，你能打开仓库指着 JSON/dashboard 说"这是怎么测的"——这本身就是工程结果证明。

另一个前提要诚实面对：这是个人项目，没有真实生产流量。所以数字的正确来源是 **benchmark、评估集、压测、消融实验（A/B before-after）**，而不是编造"服务了 X 万用户"。这类数字在面试中反而更有说服力，因为它证明你有"测量与评估"的工程习惯——这正是 Agent 工程岗位最看重的能力。

---

## 2. 简历逐条 bullet 的量化补法

对照 `resume.md` 的六条 bullet，每条给出：该补什么数字 → 怎么用现有项目测出来 → 需要新做什么。

### 2.1 Workflow + Sub-Agent 混合架构

**可补数字：**
- 主流程 graph 节点数、支持的中断/恢复场景数（3 类审批中断：要素确认、计划确认、修改目标确认）
- 端到端流程稳定性：N 次完整"需求→设计→产物"流程的成功率
- 中断恢复成功率：构造 checkpoint 中断后恢复的测试，统计恢复成功率

**怎么测：** 写一个脚本批量跑 20~50 次标准教学设计流程（可用固定输入 + 真实模型），统计各阶段成功率与端到端耗时。埋点已存在，只需汇总。

**简历表述示例：** "主流程覆盖 X 个 graph 节点与 3 类审批中断场景，标准流程 50 次回放成功率 XX%，中断恢复成功率 XX%"。

### 2.2 双层长期记忆

**可补数字（评估集已有 8 个 memory 用例，先跑出结果）：**
- 记忆检索命中率：应加载的记忆是否被加载、不相关记忆是否被忽略（`no_irrelevant_memory.yaml` 已存在）
- 记忆写入准确率：该写才写、隐私内容不写（`memory_privacy.yaml`、`memory_not_created.yaml` 已存在）
- 个性化效果消融：同一批备课请求，开/关记忆各跑一遍，用 rubric 评分对比输出的个性化程度

**需要新做：** 把 memory 用例从 8 个扩到 15~20 个（多覆盖冲突更新、过期偏好、跨学科经验迁移），然后跑 suite 得到通过率。

**简历表述示例：** "构建含 X 个用例的记忆评估集，检索命中率 XX%、隐私内容零写入；消融实验显示开启记忆后个性化评分提升 XX%"。

### 2.3 上下文压缩（最容易出漂亮数字的一条）

**可补数字：**
- token 削减率：压缩前后消息 token 数对比（`context.compression.completed` 事件已带 size/count 字段）
- 长对话成本节约：模拟 30/50/100 轮对话，对比开关压缩下的累计 prompt token 与折算成本
- 压缩额外延迟：`duration_ms` 已埋点，直接统计
- 一致性保障：4 个 context_compression 评估用例的通过率（含审批跳过、失败回退）

**怎么测：** 写一个长对话模拟脚本（构造 50+ 轮备课对话），`CONTEXT_COMPRESSION_ENABLED` 开/关各跑一遍，从 observation 事件里汇总 token 数。这是纯本地实验，半天能做完。

**简历表述示例：** "50 轮长对话场景下 prompt token 累计降低 XX%（约 XXk → XXk），压缩额外延迟 p95 < X s，审批/中断场景零误压缩"。

### 2.4 Harness 执行层（权限/白名单/超时/重试）

**可补数字：**
- 安全拦截率：构造红队用例集（路径穿越、越权读其他 thread 文件、shell 绕过执行 python/pip、覆盖他人产物、未授权工具调用），统计拦截率。`test_auth_policy.py`、`test_workspace_manager.py` 已有部分断言，抽出来做成 20~30 条对抗用例
- 重试收益：统计 ToolRetryMiddleware 挽救的失败比例（工具调用首次失败但重试成功 / 总失败）
- 超时与截断触发的边界值（超时秒数、输出截断长度——这些是配置事实，直接写）

**简历表述示例：** "构建 X 条越权/注入/绕过对抗用例，拦截率 100%；工具级重试将瞬时失败的最终失败率从 XX% 降至 XX%"。安全类数字必须是 100% 才写，否则先修再测。

### 2.5 Sub-Agent 沙箱（本地 workspace + Daytona）

**可补数字：**
- 产物生成成功率与平均耗时：批量生成 PPT / DOCX / HTML 各 20 次，统计 ready 率、失败归因分布、平均与 p95 耗时（`artifact` 埋点已有 `duration_ms`）
- 产物修改准确率：构造 10~20 条差量修改指令，人工 rubric 评"改对目标且未破坏其余内容"的比例
- 沙箱双后端切换：本地 vs Daytona 的执行耗时对比（如果 Daytona 环境可用）

**简历表述示例：** "三类产物批量生成 60 次成功率 XX%，平均生成耗时 XX s；差量修改准确率 XX%，失败均可通过 trace 归因到 6 类错误"。

### 2.6 可观测性与评估闭环

这条目前只有"24 个评估用例"一个数字，且没有结果。要补的是**结果和闭环证明**：

- 跑通 `evals/cli.py` 全量 suite，把 `EvalReport`（passed/failed/avg_score/category_scores）JSON 存入 `backend/tests/evals/results/` 并提交仓库
- 用 `check_regression.py` 建立基线对比：至少演示一次"改动导致某用例回退→被回归检查抓住"的真实案例，这是面试讲闭环最好的故事
- 指标覆盖数量：数一下实际导出的 metrics/observation 种类（LLM、tool、RAG、artifact、ingestion、compression、storage、workspace 至少 8 类），配一张 Grafana dashboard 截图存 `docs/observability/`

**简历表述示例：** "评估闭环覆盖 4 个维度 X 个用例，整体通过率 XX%，接入回归门禁；可观测性覆盖 8 类核心事件，Grafana 大盘可按 run_id 归因失败"。

---

## 3. 需要新建的三个实验（现有设施覆盖不到的）

以下是简历上还完全没有、但对"工程结果证明"权重最高的三块：

### 3.1 并发/性能压测基线

现在简历完全没有性能数字。做法：

- 用 Locust 或 k6 压 `/api/chat/stream`（SSE）与文件上传接口，测出：单实例可稳定支撑的并发 SSE 连接数、首 token 延迟（TTFT）p50/p95、消息完整率
- RAG 检索单独压：`rag.py` 检索环节的 p95 延迟（埋点已有）
- 文件入库吞吐：批量上传 50 个文档，统计入库队列的吞吐与失败率

注意：瓶颈大概率在上游 LLM API 而非你的服务，压测报告里要把两者分开（服务自身开销 vs 模型延迟），这个区分本身就是面试加分点。

**产出数字示例：** "单实例支撑 XX 路并发 SSE 会话，首 token p95 XX s（其中服务自身开销 < XXX ms）；RAG 检索 p95 XX ms"。

### 3.2 CI 门禁（工程结果的硬证明）

企业级评估报告（`docs/enterprise-readiness-assessment.md`）已指出缺 CI。这是投入产出比最高的工程补强：

- GitHub Actions：lint + 后端 pytest + 评估 suite 冒烟子集 + 前端 build
- 把 `check_regression.py` 挂进 CI 作为评估回归门禁
- README 挂 CI badge + 测试数量/覆盖率

**产出数字示例：** "CI 集成 XX 个后端测试与评估回归门禁，主干构建通过率 100%"。GitHub 仓库首页的绿色 badge 是面试官 10 秒内就能看到的工程信号。

---

## 4. 数字的沉淀与表述规范

### 沉淀（让数字可验证）

- 所有实验结果存 `docs/benchmarks/`：每个实验一个 markdown（实验设计、环境、命令、原始数据链接、结论），评估 JSON 报告进 `backend/tests/evals/results/`
- Grafana 截图、压测报告图表一并入库
- 简历上每个数字都应该能在仓库里找到出处——面试时直接打开给面试官看

### 表述（诚实且专业）

- 用"评估集通过率 / 压测基线 / 消融对比"这类词，不用暗示生产流量的词
- 数字带条件："50 轮对话场景下"、"单实例"、"batch of 60"——带条件的数字比裸数字可信
- 每条 bullet 的结构统一为：**做了什么（已有）→ 怎么验证的（补）→ 数字结果（补）**
- 安全类只写 100% 拦截；达不到就先修
- 别堆太多数字：每条 bullet 1~2 个最有说服力的即可，其余留作面试弹药

### 修改后的 bullet 示例（以上下文压缩为例）

> 针对教师长程备课场景设计上下文压缩策略，Token 超阈值时自动摘要历史消息并保留教学元数据与近期对话；**50 轮长对话实验中累计 prompt token 降低 62%，压缩额外延迟 p95 1.8s，审批/中断场景零误压缩**（数字为示意，以实测为准）。

---

## 5. 执行优先级

按投入产出比排序：

**第一批（1~2 天，纯收割已有设施）**
1. 跑通全量 eval suite，沉淀第一份 `EvalReport` JSON → 立刻获得 4 个维度的通过率数字
2. 长对话压缩实验（开/关对比）→ token 削减率 + 延迟数字
3. 批量产物生成 60 次 → 成功率 + 耗时数字

**第二批（3~5 天）**
4. GitHub Actions CI + 回归门禁 + badge
5. 红队对抗用例集（20~30 条）→ 拦截率
6. SSE 并发压测基线（TTFT、并发数）

**第三批（1 周+，可选）**

8. 记忆消融实验 + memory 用例扩充
9. Grafana dashboard 完善 + 截图入库

做完第一批，简历上就已经能从"零数字"变成每条 bullet 至少一个实测数字；三批做完，这个项目就同时具备了"量化结果"和"评估驱动开发"两层证明——后者对 Agent 工程岗位是差异化竞争力。

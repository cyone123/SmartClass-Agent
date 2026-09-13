我查了截至 **2026 年 9 月 8 日** 仍在活跃演进的一批 Agent Memory / Context Engineering 项目和官方设计资料，重点看了 **Hermes Agent、Mem0、OpenViking、Zep/Graphiti、Letta/MemGPT、LangGraph/LangMem**。结论其实相当明确：

> 现在成熟的 Agent 长期记忆，已经基本告别了“聊天记录全部 embedding → Vector DB → 每轮 top-k RAG”这种简单方案。
>
> 2026 年更主流的架构正在收敛成：**短期工作记忆 + 少量常驻核心记忆 + 结构化长期记忆 + 情景/经验记忆 + 原始历史归档 + 分层检索 + 后台记忆整理**。

而且“Memory”本身正在从一个 `VectorStore`，升级为一个完整的 **Context Management / Memory State Management 子系统**。

------

# 一、先给结论：目前最值得关注的六条路线

我把这些系统按“设计哲学”而不是产品名字分类：

| 路线                       | 代表项目                | 核心思想                                                     | 当前成熟度/适用面  |
| -------------------------- | ----------------------- | ------------------------------------------------------------ | ------------------ |
| 小型常驻记忆 + 历史归档    | **Hermes Agent**        | 极少重要信息直接常驻 Prompt，其余历史按需搜索                | ⭐⭐⭐⭐⭐ 非常务实     |
| Fact Memory Service        | **Mem0**                | 对对话提取原子事实，独立 Memory Service 管理                 | ⭐⭐⭐⭐⭐ 最容易集成   |
| Hierarchical Context DB    | **OpenViking**          | Memory / Resource / Skill 全部文件系统化、分层加载           | ⭐⭐⭐⭐⭐ 很值得关注   |
| Temporal Knowledge Graph   | **Zep / Graphiti**      | 实体 + 关系 + 时间演化图                                     | ⭐⭐⭐⭐ 企业场景强    |
| Memory-first Agent Harness | **Letta / MemGPT**      | Agent 自己管理上下文，Memory 是 Harness 核心能力             | ⭐⭐⭐⭐ 前沿程度高    |
| Memory Primitives          | **LangGraph / LangMem** | 提供 Store、Namespace、Semantic/Episodic/Procedural Memory 原语 | ⭐⭐⭐⭐⭐ 工程生态成熟 |

这里所谓“主流”不是严谨的市场份额排名，因为目前根本没有可信的 Agent Memory 市场占有率统计。我主要结合了架构影响力、项目活跃度、框架集成度和社区规模。比如目前 LangGraph GitHub 约 37.4k stars、OpenViking 约 35.9k、Letta 主项目约 24.6k；Mem0 已经是这一垂类最有影响力的独立 Memory 项目之一。GitHub stars 只能看社区热度，不能直接等同生产使用量。([GitHub](https://github.com/langchain-ai/langgraph?utm_source=chatgpt.com))

------

# 二、Hermes Agent：一个很值得参考的“朴素但正确”的设计

Hermes 的设计尤其值得 Agent Harness 开发者研究，因为它没有一上来就把所有问题交给 Vector DB。

Hermes 内建两份长期记忆：

```text
MEMORY.md
USER.md
```

而且非常小：

```text
MEMORY    2200 chars
USER      1375 chars

总共大约 1300 tokens
```

它们在 session 开始时直接注入 System Prompt，并且这个 snapshot 在整个 session 中保持不变。Agent 可以通过工具增加、替换、删除 Memory，但修改后的内容要到下一次 session 才进入 Prompt。一个重要原因是这样可以保持 Prompt Prefix 稳定，从而利用 prefix caching。([GitHub](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md))

这背后的思想非常重要：

> **真正重要且高频使用的 Memory，不应该每轮通过 RAG 找回来。**

比如：

```text
用户使用 TypeScript
用户项目使用 pnpm
用户偏好简洁回答
当前项目是一个 Agent Harness
```

这种信息只占几百 token，却几乎每轮都可能有用。

Hermes 直接 Pin 到 Context。

但“上个月我们讨论过某个 Redis bug”这种东西，没有必要一直放进去。

所以 Hermes 另外保留：

```text
SQLite
  └── sessions
       └── messages

FTS5 Full Text Search
```

所有历史 session 都保存下来，需要的时候 Agent 自己搜索。官方设计中，长期 Pin Memory 约 1300 tokens，而历史 Session Search 可以近似无限增长，而且返回的是原始消息，不需要先做 LLM 摘要。([GitHub](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md))

于是形成：

```text
             ┌───────────────┐
             │ System Prompt │
             │ MEMORY / USER │ ← 高频、重要、少量
             └───────┬───────┘
                     │
                  Agent
                     │
                     ↓
          ┌────────────────────┐
          │ SQLite Session DB  │ ← 完整历史
          │ FTS5 Search        │
          └────────────────────┘
```

这其实已经是一个非常成熟的基础架构。

更有意思的是，Hermes 现在进一步提供 **Memory Provider 插件层**，Mem0、OpenViking 等可以作为外部 Memory Provider 接进来。因此它没有试图让自己的 MEMORY.md 解决全部长期记忆问题，而是：

```text
Built-in Core Memory
        +
Session Archive
        +
External Memory Provider
```

比如 Hermes 对 Mem0 的集成就可以让 Mem0 自动做 LLM fact extraction、semantic search、rerank、dedup。([GitHub](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory-providers.md))

这是我非常推荐的一种 Harness 架构。

------

# 三、Mem0：目前最典型的“Memory Service”路线

如果说 Hermes 是 Harness 内部的 Memory，那么 Mem0 基本代表了另一条路线：

> **把 Memory 做成类似数据库一样的独立基础设施。**

典型调用逻辑变成：

```text
Conversation
     │
     ↓
┌─────────────┐
│ Mem0.add()  │
└──────┬──────┘
       │
   Memory Extraction
       │
       ↓
  Long-term Store


新请求
  │
  ↓
Mem0.search()
  │
  ↓
Relevant Memories
  │
  ↓
LLM Context
```

Mem0 一个非常重要的变化发生在 **2026 年 4 月的新 Memory Algorithm**。

它的主 pipeline 不再坚持传统：

```text
ADD
UPDATE
DELETE
NOOP
```

而改成了更加历史友好的：

```text
Single-pass ADD-only extraction
```

即一次 LLM extraction，新记忆不断积累，核心 extraction path 不覆盖旧记录。与此同时它引入：

```text
Semantic similarity
      +
BM25
      +
Entity Matching
      +
Temporal Reasoning
```

进行 Multi-Signal Retrieval，而不是单纯 Vector Search。([GitHub](https://github.com/mem0ai/mem0))

这是一个很值得注意的设计变化。

比如用户说：

```text
2025:
I live in Shanghai.

2026:
I've moved to Seattle.
```

简单“UPDATE 上海→Seattle”会丢掉历史状态。

而 Agent 实际经常会问：

```text
Where does the user live now?

Where did the user live last year?
```

所以更合理的是：

```text
Fact A:
lives_in(user, Shanghai)
valid_at: 2025

Fact B:
lives_in(user, Seattle)
valid_at: 2026
```

旧事实可以被标记：

```text
superseded = true
superseded_by = Fact B
```

而不是物理删除。Mem0 目前的 Dream consolidation 就采用了这种 supersede 思路。([Mem0](https://mem0.ai/blog/dream-background-memory-consolidation-for-ai-agents))

------

# 四、Mem0 的另一个变化：Vector Memory 正在变成 Entity Memory

2026 年的 Mem0 已经加入原生 Graph Memory。

但它目前并不是传统意义上的：

```text
Person
 └──WORKS_AT──> Company
```

这种严格 Schema Knowledge Graph。

它更接近：

```text
Memory 1 ── Alice
Memory 2 ── Alice ── Project X
Memory 3 ── Project X
```

Memory 中提取 entity，然后通过 entity co-occurrence 建立联系。

查询 Alice 时：

```text
Semantic Score
+
BM25 Score
+
Entity Graph Boost
```

共同决定结果排序。

也就是说 Graph 主要参与 **retrieval ranking**，而不是改变 API 的返回结构。官方也明确说明，目前这个 Graph 更偏 schema-free entity linking，而不是显式 typed relationship graph。([GitHub](https://github.com/mem0ai/mem0/blob/main/docs/platform/features/graph-memory.mdx))

所以 Mem0 可以理解为：

```text
       SQL / Memory Store
            │
    ┌───────┼─────────┐
    ↓       ↓         ↓
 Vector    BM25     Entity Graph
    │       │         │
    └───────┼─────────┘
            ↓
       Retrieval Fusion
            ↓
          Rerank
```

这基本就是目前通用 Agent Memory Service 的主流方向。

------

# 五、一个越来越重要的新模块：Memory Consolidation

长期运行之后，Memory 必然会变成这样：

```text
prefers dark mode
likes dark UI
usually chooses dark theme
prefers dark themes on apps
...
```

甚至：

```text
lives in Shanghai
lives in Beijing
lives in Seattle
```

如果只会：

```text
add memory
```

Memory DB 一定逐渐腐化。

这也是 2026 年一个非常明显的趋势：

> Memory 系统开始出现类似数据库 VACUUM / LSM Compaction 的后台维护任务。

Mem0 在 2026 年 8 月发布的 Dream 就是在后台执行：

```text
Deduplicate
Merge
Supersede
Summarize
Generalize
```

例如多条：

```text
User wakes at 6am.
User attends yoga before work.
User avoids late-night meetings.
```

长期可以归纳成更高阶 Memory：

```text
User maintains an early-morning routine
and generally protects morning exercise time.
```

Mem0 官方也明确把它类比为数据库 maintenance process：在线路径快速写入，后台再做维护。([Mem0](https://mem0.ai/blog/dream-background-memory-consolidation-for-ai-agents))

我认为这是未来 Agent Memory 几乎必备的组件。

------

# 六、OpenViking：非常不同的一条路线——Context Database

OpenViking 是这批项目里我认为**最值得 Agent Harness 开发者重点研究**的一个。

因为它提出的问题已经不是：

> “Memory 应该存在哪里？”

而是：

> “Agent 所需要的所有 Context，为什么要分别放在 Memory DB、Vector DB、Skill Directory、Document Store 里面？”

所以 OpenViking 把：

```text
Memory
Resource
Skill
```

全部统一进一个虚拟文件系统：

```text
viking://
```

Agent 看到的可以类似：

```text
viking://
├── resources/
│   └── my_project/
├── user/
│   └── 123/
│       ├── memories/
│       ├── skills/
│       └── sessions/
```

这已经不太像“Memory DB”。

它更像：

> **Agent Context Database / Context File System**

([GitHub](https://github.com/volcengine/OpenViking))

------

# 七、OpenViking 最核心的设计：L0 / L1 / L2

这点尤其漂亮。

一个大型资源不是：

```text
document -> chunks -> embedding
```

而是具有三个信息密度层级：

```text
L0 Abstract
≈ 100 tokens

L1 Overview
≈ 2k tokens

L2 Full Content
完整内容
```

例如：

```text
viking://resources/project/
│
├── .abstract       ← L0
├── .overview       ← L1
│
└── docs/
    ├── .abstract
    ├── .overview
    └── architecture.md   ← L2
```

Agent 首先看：

```text
L0
```

觉得可能相关，再看：

```text
L1
```

真的需要细节，才加载：

```text
L2
```

这就是现在越来越常见的一个概念：

> **Progressive Disclosure**

而不是：

> 一搜索就把 top-10 chunk 全塞进 Prompt。

([GitHub](https://github.com/volcengine/OpenViking))

------

# 八、OpenViking 的 Retrieval 已经更像 Query Planner

OpenViking 的复杂搜索首先让一个 Intent Analyzer 判断：

```text
当前到底需要什么？
```

它可以生成 0~5 个 TypedQuery：

```text
TypedQuery {
    query
    context_type: MEMORY | RESOURCE | SKILL
    intent
    priority
}
```

例如：

> “根据我之前写 RFC 的习惯，帮我为这个服务写一份 RFC。”

可能被拆成：

```text
MEMORY
→ user's RFC preferences

SKILL
→ create RFC

RESOURCE
→ project architecture
```

然后：

```text
Intent Analysis
      ↓
Typed Queries
      ↓
Hierarchical Retrieval
      ↓
Directory recursion
      ↓
Rerank
      ↓
Relevant Context
```

而简单寒暄甚至可以产生 **0 个 retrieval query**。

这是非常重要的一个设计思想：

> **不要默认每一轮都访问长期记忆。**

([OpenViking](https://docs.openviking.ai/en/concepts/07-retrieval))

------

# 九、OpenViking 的长期记忆写入，也不是“把聊天 embedding”

Session commit 时流程大概是：

```text
Messages
   ↓
Compress
   ↓
Archive
   ↓
Memory Extraction
   ↓
Candidate Memories
   ↓
Vector Prefilter
   ↓
LLM Dedup
   ↓
Create / Merge / Delete / Skip
   ↓
Storage + Vector Index
```

它还区分：

```text
profile
preferences
entities
events
identity
soul
cases
trajectories
experiences
...
```

因此：

> “用户喜欢 TypeScript”

和：

> “上次解决 Redis 热 key 问题时，通过 local cache + request coalescing 成功解决”

不会被当成同一种 Memory。

后者可以成为：

```text
case
trajectory
experience
```

供 Agent 今后解决类似问题时使用。([OpenViking](https://docs.openviking.ai/en/concepts/08-session))

而且每次 Session Commit 都可以生成 `memory_diff.json`，记录：

```text
ADD
UPDATE
DELETE
SKIP
```

方便审计与回滚。

这是非常典型的“Memory Governance”思路。

------

# 十、Zep / Graphiti：长期记忆的另一条重要路线——Temporal Knowledge Graph

如果你的 Agent 面对的是：

```text
人
公司
项目
订单
客户
设备
账户
关系
事件
```

那么“Fact List + Vector DB”很快会遇到瓶颈。

这就是 Graphiti 的强项。

Zep / Graphiti 将历史构造成：

```text
Entity Node
Relationship Edge
Episode Node
```

例如：

```text
Alice
  │
  ├── works_at ──> OpenAI
  │
  └── manages ──> Project X
```

但最重要的是：

```text
Edge {
    valid_at
    invalid_at
}
```

也就是说知识不是静态的。

例如：

```text
Alice --works_at--> Google
valid: 2023-2025

Alice --works_at--> OpenAI
valid: 2025-
```

它会保留历史变化，而不是简单覆盖旧事实。Zep 官方的 temporal knowledge graph 就是围绕这种 changing relationships / historical context 构建的。([Zep](https://help.getzep.com/graph-overview))

Graphiti 的 retrieval 同样不是 Graph traversal 一条路，而可以组合：

```text
Semantic
+
BM25
+
Graph
+
RRF
+
Entity distance
```

([Zep](https://help.getzep.com/graphiti/working-with-data/searching))

所以它非常适合：

```text
CRM Agent
Customer Support Agent
Sales Agent
Enterprise Knowledge Agent
Project Management Agent
```

这些强 entity / relationship / temporal 场景。

------

# 十一、Letta / MemGPT：Memory 不应该是插件，而应该属于 Harness

Letta 的设计哲学比 Mem0 更激进。

它认为：

> Agent Memory 从根本上是 Agent Harness 对 Context 和 State 的管理，而不仅仅是一个 Retrieval Plugin。

因为真正决定 Agent“记得什么”的，不只是：

```text
memory.search()
```

还有：

```text
System Prompt 放什么？
哪些 Context 始终 Pin？
Compaction 后什么保留？
Agent 能修改哪些 instructions？
Skills 怎么暴露？
过去交互怎么查询？
文件系统怎么进入 Context？
```

这些其实全部属于 Harness。([Letta](https://www.letta.com/blog/why-memory-isnt-a-plugin/))

这和你之前关注的 **Agent Harness Context Compression** 是直接连起来的：

> **Memory、Compaction、Context Retrieval、Skill Loading，本质上逐渐变成同一个 Context Engineering 问题。**

这是我认为非常重要的认知转变。

------

# 十二、Letta 2026 年的新方向：Context Repository

Letta Code 现在甚至直接把 Memory 变成一个：

```text
Git Repository
```

Agent 可以自己：

```text
ls
cat
grep
mv
mkdir
rewrite
```

管理 Memory。

比如：

```text
memory/
├── system/
│   ├── identity.md
│   └── current-project.md
│
├── preferences/
│   └── coding.md
│
├── projects/
│   ├── agent-harness.md
│   └── scheduler.md
│
└── experiences/
    └── debugging.md
```

其中：

```text
system/
```

始终进入 Prompt。

其他文件：

```text
按需加载
```

目录树和 frontmatter description 则一直作为导航信息暴露给 Agent。

这同样是 Progressive Disclosure。([Letta](https://www.letta.com/blog/context-repositories/))

而且因为它是 Git：

```text
Memory Change
      ↓
Git Commit
      ↓
Version History
      ↓
Rollback / Diff
```

多个 Memory Sub-Agent 甚至可以开 Worktree 并行整理 Memory，然后 Merge。([Letta](https://www.letta.com/blog/context-repositories/))

对于 Coding Agent，我认为这种：

> **Filesystem + Git + Agent-native tools**

是非常有潜力的一条路线。

------

# 十三、Letta 的另一个重要思想：Sleep-time Memory Agent

Memory 整理其实不应该卡在用户响应链路里。

旧 MemGPT：

```text
User
 ↓
Agent
 ↓
Memory Management
 ↓
Tool
 ↓
Answer
```

容易导致延迟和 Agent 分心。

Letta 后来拆成：

```text
             ┌── Primary Agent ──→ User
             │
Conversation ┤
             │
             └── Sleep-time Agent
                       ↓
                    Reflect
                       ↓
                 Consolidate
                       ↓
                  Rewrite Memory
```

Primary Agent 用更快的模型。

Sleep-time Agent 可以用更强、更慢、更便宜的异步计算去做：

```text
reflection
deduplication
reorganization
memory rewriting
document ingestion
```

官方解释也是把 memory management 从在线对话路径卸载到异步 sleep-time agent。([Letta](https://www.letta.com/blog/sleep-time-compute/))

你会发现这和 Mem0 2026 年的 **Dream** 非常接近。

这说明两条独立演进路线正在收敛：

```text
Letta:
Sleep-time Agent

Mem0:
Dream

OpenViking:
Async Session Extraction
```

共同指向：

> **Foreground Agent + Background Memory Worker**

------

# 十四、LangGraph / LangMem：目前最标准的 Memory Taxonomy

如果讨论理论和工程接口，我很推荐 LangGraph 的分类：

```text
Short-term memory
Long-term memory
```

Long-term 又分：

```text
Semantic Memory
Episodic Memory
Procedural Memory
```

([Docs by LangChain](https://docs.langchain.com/oss/python/concepts/memory))

它们分别是什么？

### Semantic Memory

“知道什么”。

例如：

```text
User prefers TypeScript.
User's project uses PostgreSQL.
Project deadline is September 20.
```

------

### Episodic Memory

“以前发生过什么 / 怎么成功解决过问题”。

例如：

```text
Situation:
Redis latency increased.

Action:
Added local cache and request coalescing.

Result:
P99 dropped from 500ms to 80ms.
```

这种 Memory 对 Coding Agent / Autonomous Agent 非常有价值。

------

### Procedural Memory

“应该怎么做”。

例如：

```text
When implementing API changes:
1. modify schema
2. update tests
3. run integration tests
4. update docs
```

它实际上已经非常接近：

```text
Skill
SOP
Prompt
Policy
```

所以也再次说明：

> **Memory 和 Skill 的边界正在越来越模糊。**

LangGraph 自身则比较克制，它主要提供：

```text
Store
Namespace
Key
Checkpoint
Semantic Search
```

长期记忆是 JSON documents，以自定义 namespace 做作用域隔离。([Docs by LangChain](https://docs.langchain.com/oss/python/langchain/long-term-memory))

它更适合：

> “我要自己设计 Memory System。”

而 Mem0 更像：

> “我希望直接有一个 Memory System。”

------

# 十五、把这些项目放在一起，会发现行业正在收敛成这套架构

我认为目前比较先进、也最具有通用性的 Agent Memory Architecture，可以抽象成：

```text
                        ┌──────────────────────┐
                        │     Agent Harness    │
                        └──────────┬───────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
            ▼                      ▼                      ▼
     Working Memory          Core Memory           Context Router
     当前 Session             always pinned              │
                                                    ┌─────┼─────┐
                                                    │     │     │
                                                    ▼     ▼     ▼
                                               Semantic Episodic Skill
                                                Memory   Memory Memory
                                                    │
                                                    ▼
                                           Hybrid Retrieval Layer
                                      Vector + BM25 + Entity + Temporal
                                                    │
                                                    ▼
                                                Reranking
                                                    │
                                                    ▼
                                         Progressive Disclosure
                                              L0 → L1 → L2
                                                    │
                                                    ▼
                                              Context Window


Conversation / Tool Trace
          │
          ▼
      Raw Archive
          │
          ▼
 Background Memory Worker
          │
   ┌──────┼────────┬───────────┐
   ▼      ▼        ▼           ▼
Extract  Dedup  Supersede   Reflect
   │      │        │           │
   └──────┴────────┴───────────┘
                  │
                  ▼
             Memory Store
```

这基本就是我这次调研后认为 **2026 年 Agent 长期记忆系统正在形成的“标准答案”**。

------

# 十六、其中有 8 个已经非常明确的设计原则

1. **不要把完整聊天历史当长期记忆。** 原始历史应该保留，但作为 Archive；长期 Memory 应该是对历史进行筛选、提取或整理后的高价值信息。
2. **一定保留少量 Always-on Core Memory。** Identity、稳定偏好、当前长期项目等，不应该每轮依赖 RAG 碰运气找回来。Hermes 的 1k 左右 token Memory 是很好的例子。
3. **Memory 必须 Typed。** 至少应区分 Semantic / Episodic / Procedural；复杂系统进一步拆 Profile、Preference、Entity、Event、Case、Trajectory、Skill。
4. **Retrieval 不应该只用 Vector Similarity。** 当前成熟方案普遍走 Hybrid Retrieval：Embedding + BM25 + Metadata + Entity/Graph + Temporal，再做 fusion/rerank。Mem0、Graphiti 都明显在这个方向。([GitHub](https://github.com/mem0ai/mem0))
5. **必须有时间与历史语义。** “事实过期”不应该等价于“事实从未发生”。`valid_at / invalid_at / superseded_by` 会越来越重要。
6. **必须 Progressive Disclosure。** 先判断目录/Abstract 是否相关，再逐渐加载 Overview 和完整内容，而不是一次性 top-k chunk 全注入。OpenViking 和 Letta Context Repository 都体现得非常明显。([GitHub](https://github.com/volcengine/OpenViking))
7. **写 Memory 最好异步化。** 在线路径做快速 logging；后台 Worker 再 extraction、dedup、reflection、consolidation。Mem0 Dream、Letta Sleep-time、OpenViking Session Commit 都说明了这一趋势。([Mem0](https://mem0.ai/blog/dream-background-memory-consolidation-for-ai-agents))
8. **Memory 必须可治理。** 要有 namespace / tenant isolation、provenance、audit、diff、rollback、forget/delete、secret filtering 和写入权限，而不能只是一个黑盒 Vector DB。

------

# 十七、现在不同项目到底应该怎么理解

我会把它们画成这张“技术光谱”：

```text
        简单                                  完整 Context OS
         │                                         │
         ▼                                         ▼

Hermes       Mem0       Zep       OpenViking      Letta
  │            │         │            │             │
Pinned       Fact      Temporal    Context DB     Memory-first
Memory       Memory    Graph       Filesystem     Harness
+
History
```

但这不是互斥关系。

实际上真正有意思的生产架构很可能是：

```text
Agent Harness
│
├── Core Memory
│
├── Session State
│
├── Context Compaction
│
├── Memory Provider Interface
│
└── External Memory Backend
       │
       ├── Mem0
       ├── OpenViking
       └── Graphiti
```

Hermes 已经在实际采用这种思想。

------

# 十八、如果现在让我从零设计一个 Agent Harness

我不会直接：

```text
messages
   ↓
embedding
   ↓
Qdrant
```

而会设计成：

```text
Memory System

├── 1. Working Memory
│     └── 当前 session / checkpoint
│
├── 2. Core Memory
│     ├── agent_identity
│     ├── user_profile
│     └── active_project
│
├── 3. Long-term Semantic Memory
│     ├── facts
│     ├── preferences
│     ├── entities
│     └── events
│
├── 4. Episodic Memory
│     ├── cases
│     ├── trajectories
│     └── experiences
│
├── 5. Procedural Memory
│     ├── skills
│     ├── SOP
│     └── learned instructions
│
└── 6. Raw Archive
      ├── messages
      ├── tool calls
      ├── artifacts
      └── execution traces
```

底层存储我会采用：

```text
PostgreSQL / Document Store
        ← source of truth

Vector Index
        ← semantic recall

FTS / BM25
        ← exact + lexical recall

Entity / Temporal Index
        ← relationship + state evolution

Filesystem / Object Storage
        ← large context / docs / skills / traces
```

而不是试图让某一个 Vector DB 同时承担所有职责。

------

# 十九、Retrieval Pipeline 我会这样设计

```text
User Query
     │
     ▼
Memory Router
     │
     ├── Need memory?
     │       └── No → skip
     │
     ▼
Query Planning
     │
     ├── semantic?
     ├── episodic?
     ├── skill?
     └── resource?
     │
     ▼
Scope Filter
user / agent / project / workspace
     │
     ▼
Hybrid Recall
Vector + BM25 + Entity + Temporal
     │
     ▼
Reranker
     │
     ▼
Memory Policy
freshness
importance
confidence
provenance
token budget
     │
     ▼
Progressive Disclosure
L0 → L1 → L2
     │
     ▼
Prompt
```

这里最容易被很多初级 Memory 系统忽视的其实是第一步：

```text
Need memory?
```

比如：

> 你好

根本没有必要做一次 Vector Search。

而：

> 上次我们那个数据库设计为什么最终选 PostgreSQL？

才应该触发 memory retrieval。

OpenViking 已经显式允许 Intent Analyzer 返回 0 query，就是这个思想。([OpenViking](https://docs.openviking.ai/en/concepts/07-retrieval))

------

# 二十、Write Pipeline 则应该和 Retrieval 完全分开

建议：

```text
Conversation
      │
      ├──────────────→ Raw Event Store
      │
      └──────────────→ Async Memory Queue
                              │
                              ▼
                         Extractor
                              │
                     Candidate Memories
                              │
                              ▼
                         Importance Gate
                              │
                              ▼
                      Similarity Recall
                              │
                              ▼
                     Conflict Resolution
                   ┌──────────┼──────────┐
                   ▼          ▼          ▼
                  ADD       MERGE     SUPERSEDE
                   │          │          │
                   └──────────┴──────────┘
                              │
                              ▼
                         Memory Store
```

重点是：

> **Logging ≠ Remembering。**

每件事情可以记录，但只有少部分东西值得成为长期记忆。

否则 Agent 用一年之后，你会得到几百万条几乎无意义的“Memory”。

------

# 二十一、我认为最值得特别关注的两个新趋势

第一个是：

> **Memory 正从 Retrieval System 变成 Evolving State System。**

过去：

```text
Store
Search
```

现在：

```text
Store
Extract
Merge
Supersede
Forget
Reflect
Generalize
Reorganize
Search
```

它越来越像一个有后台 maintenance 的数据库。

第二个是：

> **Memory 正从 Vector DB 回到 Filesystem / Hierarchy。**

OpenViking：

```text
viking:// filesystem
```

Letta：

```text
Git Context Repository
```

Coding Agent 中各种：

```text
AGENTS.md
SKILL.md
CLAUDE.md
memory/*.md
```

其实都在说明：

**Agent 对层级目录、文件名、description、grep、read 的使用能力非常强。**

所以未来很可能不是：

```text
Vector DB
vs
Filesystem
```

而是：

```text
Filesystem / Document DB = canonical context
          +
Vector / BM25 / Graph = indexes
```

这正是 OpenViking dual-layer storage 的做法：AGFS 保存内容作为单一事实来源，Vector Index 只保存 URI、vector 和 metadata。([OpenViking](https://docs.openviking.ai/en/concepts/01-architecture))

我认为这是非常漂亮、也非常“数据库工程化”的设计。

------

# 二十二、最终给这些方案一个实际选型建议

| 你的场景                             | 优先研究                                                     |
| ------------------------------------ | ------------------------------------------------------------ |
| 普通聊天助手、AI SaaS 个性化         | **Mem0**                                                     |
| 希望最快给现有 Agent 增加记忆        | **Mem0**                                                     |
| 自己开发 Agent Harness               | **Hermes + OpenViking + Letta**                              |
| Coding Agent                         | **OpenViking / Letta Context Repository / Hermes**           |
| 长时间 Autonomous Agent              | **OpenViking + Letta 思路**                                  |
| CRM / Customer Support / Sales Agent | **Zep / Graphiti**                                           |
| 大量实体关系、状态随时间变化         | **Graphiti**                                                 |
| 已经基于 LangGraph                   | **LangGraph Store + LangMem**                                |
| 本地轻量 Agent                       | **Hermes 的 Core Memory + SQLite FTS**                       |
| 企业级通用 Memory Platform           | **Mem0-style Service + Graph/Temporal + background consolidation** |

如果你的目的不是“选一个库来用”，而是像你之前研究 Agent Harness Context Compression 那样，想真正搞懂并自己设计 Agent Harness，那么我建议重点阅读顺序是：

**Hermes → OpenViking → Mem0 → Letta → Graphiti → LangMem**。

因为这样刚好能看到长期记忆系统从：

```text
Pinned Notes
    ↓
Session Archive
    ↓
Fact Memory
    ↓
Hierarchical Context DB
    ↓
Temporal Graph
    ↓
Self-evolving Context
```

整个设计空间。

尤其值得记住一句：

> **现代 Agent 的长期记忆，本质已经不是“怎么保存历史对话”，而是“如何让一个长期运行的 Agent 持续维护一个有限、准确、可演化、可检索、可审计的世界状态与经验库”。**

这也是为什么我认为更准确的术语正在从 **Agent Memory** 向 **Context Engineering / Context Database / Persistent Agent State** 演化。

如果你接下来准备进一步做 Agent Harness 设计，我建议下一步直接研究一个更具体的问题：**“Context Compression 与 Long-term Memory 到底如何协同”**——例如一次 context compaction 时，哪些信息只进入 session summary，哪些 promote 为 long-term memory，哪些进入 episodic experience，哪些应该永久丢弃。这实际上正好把你前面研究的上下文压缩和这次长期记忆串成一套完整 Harness 架构。

这个领域变化很快。我也可以定期跟踪 Hermes、OpenViking、Mem0、Letta、Graphiti 等项目的新 release 和架构变化，并在有明显的新 Memory 设计出现时给你一份摘要。
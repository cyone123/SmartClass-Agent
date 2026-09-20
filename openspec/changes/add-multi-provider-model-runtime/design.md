## Context

动机和范围见 [proposal.md](proposal.md)。本设计基于 2026-09-19 的仓库检查与上轮官方资料/开源源码调研；调研未执行真实模型测试，以下能力须经固定版本的契约测试和 smoke 验证。

- `app/core/llm.py` 直接创建 ChatOpenAI，并在 import 时实例化 main、structured、fast、memory；memory/compression 的 model、key、URL 分别回退。
- `graph.py`、`memory.py` 在模块级绑定工具。`agent.py` 创建并持有 Agent runnable，`video_transcribe.py` 独立缓存视觉模型。仅改变模型构造函数无法解决配置陈旧问题。
- `ModelRuntime` 已承担记忆合成、调用和部分 fallback，保留此调用边界。主图动作协议是工具调用，不应在接入厂商时改为普通 JSON 文本。
- `AgentRun` 当前没有模型配置字段；审批恢复产生新 run。`MemoryReflectionJob.snapshot` 为版本化 JSON，适合携带反思角色的配置快照。
- LangGraph checkpoint 是内部运行历史，前端历史接口和 SSE 是展示出口；二者不得共用一个有损的消息简化过程。
- 现有 context-compression、durable-chat-runs、evaluation-harness-integrity 规范仍有效；本变更新增约束，不改变审批、断线续传或证据门禁语义。

## Goals / Non-Goals

**Goals:**

- 让业务按角色获取模型，厂商参数与客户端选择只存在于模型接入包。
- 建立稳定配置 ID、快照版本和替换配置存储的接口，一期以重启为配置生效边界。
- 使“配置可加载”“协议调用可用”“能力经验证”“教学业务回归通过”成为独立验收层。

**Non-Goals:**

- 不引入 LiteLLM 服务、Dify 插件执行环境或新 Agent 框架；不实现自选最优模型、计费路由或任意跨协议中途切换。
- 不实现配置管理数据库表、前端页面、管理 API 或热更新。运行快照所需的数据库迁移属于本期。
- 不扩展 Vertex/Bedrock/Azure 特殊鉴权、Responses/Interactions API、原生视频上传、服务端内置搜索/代码工具。
- embedding/STT 仅保证原行为，独立于聊天角色工厂；embedding 变更及向量重建另开提案。

## Decisions

### 1. 保留 LangChain，以协议适配器封装提供商差异

新增建议包 `app/core/model_access/`，包含 schemas、registry、resolver、config_repository、secrets、factory、messages、errors 与 adapters。工厂产出 BaseChatModel，复用已有 ModelRuntime；`llm.py` 保留兼容包装函数，不保留模块级模型对象。

```text
Graph / Agent / Memory / Compression / Video
                      |
                ModelRuntime
                      |
             Role Resolver + Factory
                /             \
      ConfigRepository     ProviderRegistry
             |                   |
      File + Env snapshot    Presets + Rules
                      |
              Protocol Adapters
            /         |         \
      openai_chat  anthropic  google_genai
```

`openai_chat` 默认使用 ChatOpenAI；`anthropic_messages` 使用 ChatAnthropic；`google_genai` 使用 ChatGoogleGenerativeAI，并显式选择 Gemini Developer API，防止宿主机 Google 环境变量隐式切换云平台。DeepSeek 专用实现可在 openai_chat 适配器内使用 ChatDeepSeek，选择依据是 reasoning 字段完整往返的契约结果，不依据模型名称动态猜测厂商。

替代方案：LiteLLM 对大量供应商和网关治理更有价值，但本期增加转换链；自行封装 SDK 则需重写 LangChain 工具/消息能力。采用原生集成并维护小型兼容策略，避免以上成本。

### 2. 配置分五层，预设不等于连接

| 对象 | 主要字段 | 约束 |
|---|---|---|
| Protocol | 稳定协议 ID、适配实现 | 不根据 model_id/URL 子串猜测 |
| ProviderPreset | ID、默认端点、支持协议、credential/parameter schema、能力规则版本 | 声明式数据；敏感 header 只接受凭据引用 |
| Connection | ID、preset、protocol、endpoint、credential references、连接选项 | 同一预设允许多个账号；未知预设/协议组合报错 |
| ModelProfile | ID、connection、model_id、参数、能力覆盖 | 与长期记忆 Profile 无关；支持自定义模型 ID |
| RoleBinding | model 或 inherit、显式 fallback 列表 | model 与 inherit 互斥；完整继承并检查环 |

一期配置入口为 `MODEL_CONFIG_PATH` 指向的 YAML；相对路径按明确的仓库配置根解析，容器通过只读挂载传入。文件格式含 `version: 1`、connections、models、roles。敏感值只来自 `env:NAME` 引用；端点拒绝 userinfo 和敏感 query，认证 header 放入凭据 schema，不藏在任意参数中。

配置优先级：角色显式 YAML 定义 > 该角色旧环境变量映射 > 既定未配置角色继承。YAML 角色一旦显式定义，只在 YAML 配置图和预设默认值内解析，不从旧环境变量填补身份字段。模型参数按预设默认值 → model profile 显式值解析；不支持的显式参数失败，不能静默丢弃。

旧环境变量未迁移时生成合成连接和模型配置：完整三元组保留；仅同一角色既有固定官方默认端点可由预设补齐，不从别的角色借 key/URL。专用角色完全未配置时才继承。memory 保持 fast → structured → small → main 候选顺序，compression 优先 memory 链，fast 保持 small 候选；main/structured/small 原先没有的自动回退不新增。部分身份配置失败并给出迁移建议；仅 timeout 等非身份选项可在解析完整父配置后覆盖。

启动校验配置结构与启用的必需角色。禁用的可选视觉、压缩、STT 路径不要求提供凭据；压缩模型初始化/调用失败仍按原规范保留对话并报告压缩失败。不得因可选能力未部署使普通聊天不可用。

替代方案：继续扩增每角色 PROVIDER/BASE_URL/API_KEY 环境变量无法自然支持多账号、结构化能力和表单 schema，因此 env 只作为兼容输入与密钥来源。

### 3. 能力是连接、模型、模式与适配版本的交集

能力至少包含文本/图片输入、流式、工具调用、工具选择方式、结构化方法、上下文窗口、输出上限和推理元数据往返。能力状态区分已验证支持、已知不支持、未知，保存规则来源/版本；自定义覆盖只能表达待验证声明，不能覆盖适配器确定不支持的限制。

main/附件与产物 Agent 要求工具闭环；structured/fast 按实际动作协议要求校验；memory 要求记忆工具 schema；compression 要求文本；video_vision 要求图片输入。未知模型允许作为自定义配置，但不能自动宣称强制工具或严格 schema 可用，必需能力未知时在使用前拒绝并指明需要显式配置和验证。

legacy OpenAI 配置迁移时，将原调用路径已经依赖的基础能力转为 `legacy-declared` 声明，并标记尚未实测，避免因缺少新能力字段阻断原有效部署；此声明不自动扩展到新协议、原生严格 schema 或 thinking 工具闭环。能力是否声明与是否已验证分别保存，离线验证命令不得为真实兼容性背书。

保留现有动作工具和 Pydantic 校验；纯数据提取可选择 native schema / tool calling / JSON text，策略明确记录。必需结构化任务不能无声降为无约束文本。工具 JSON Schema 保持业务定义，兼容转换不得删除必需字段或改变验证语义。

thinking 不统一成布尔值：通用配置表达 default/off/on/adaptive 等意图以及可选预算/effort，适配层按模型规则映射、拒绝无等价映射的显式要求。DeepSeek 现有关闭 thinking 行为保留在 legacy 兼容规则内；只对验证过的 profile 开启带 tools 的 thinking。OpenRouter 的 reasoning/provider 参数使用其自身语义，不套用直连 DeepSeek 的 extra_body。智谱国内标准 API、海外或 Coding 端点不能自动互换，一期内置国内标准预设。

### 4. 运行快照覆盖审批和后台任务

新增 `ResolvedModelConfigSnapshot`：schema version、配置内容指纹、能力规则版本、完整已解析非敏感连接/模型/角色配置、credential references。快照包含实际需要的全部角色和显式 fallback；无 API key、认证 header 值、宿主机路径或 SDK 实例。业务内部快照可保留无敏感信息的 endpoint，观测/前端 DTO 则排除 endpoint 和凭据引用。

在 AgentRun 增加可空 JSON 快照字段，通过迁移保持旧行可读。新运行创建时持久化快照；图状态保存当前工作流快照及独立配置工作流标识。快照只有 server-side 来源，不能从用户 chat payload 接受。执行时使用完整快照，不凭指纹重新加载当前文件，因此重启后仍可恢复旧模型选择。

固定范围：普通聊天按新 run 捕获；教学设计自启动到最终完成/取消保持固定，补充要求和审批恢复不刷新；产物修改启动新的工作流快照；明确重启教学任务也开启新工作流。并行 fan-out、补偿调用和审批产生的新 run 共享当前工作流快照。后台反思在入队时捕获源任务中已固定的 memory 配置；worker 不重新读取全局角色。

若入口意图需要模型识别，不能在识别出“重启任务”之后才读取新的全局配置。运行快照封套在接纳时同时固定当前配置与已有工作流配置（相同指纹可去重）；入口在已有工作流配置下识别，确认新工作流动作后选择封套中预先固定的当前配置供新任务使用，并持久化选择事件。原快照不修改，动作完成前不切换未结束的工具交换；调用证据记录本次请求实际选择的快照。这样同一 run 内的明确重启不会破坏快照不可变性。

旧 checkpoint/待处理反思任务无快照时，只在首次进入新运行时从当前合法配置捕获并持久化一次，记录 `legacy_snapshot_adopted` 脱敏标志；必须在任何模型请求前完成，不伪造历史配置来源。现有进程中断任务的终止规则不变。

凭据引用固定，但一期环境变量不提供历史密钥仓库：执行时解析当前引用值，轮换只改变认证值，不改变端点/模型/角色。进程内工厂使用不外泄的凭据代次隔离缓存；不存在或已撤销的凭据导致明确失败，不切换账号。这项限制写入运维文档，不能把“配置可复现”描述成“历史密钥可恢复”。

缓存键包含连接/配置版本、模型参数、能力规则版本、streaming 选项和进程内凭据代次。只共享不可变客户端基础，不在全局对象上修改 tools/headers；绑定 runnable 按配置和工具 schema 隔离。客户端由应用生命周期管理，关闭连接，避免跨事件循环复用异步客户端。

### 5. 内部消息保真，展示消息提取文本

统一文本提取只输出显式 text blocks；不对 list/dict 直接 str()。完整 AIMessage、tool calls、tool results 和厂商签名留在内部历史。验证从流增量合并、checkpoint 编解码到恢复发送的全链路，尤其是空文本但携带签名/usage 的结束块。

系统提示合并由适配边界按协议处理，保持业务系统指令、非可信记忆边界及顺序，不能简单把 system 降成 user。主图现有构建历史的过滤/截取也纳入检查，保留完整工具调用与结果组合。

跨提供商历史在完整回合边界转换：已完成旧回合可保留可移植文本与完整工具结果；不可移植厂商元数据不得伪造或作为普通文本发送。存在未完成工具往返时不允许换协议；无法安全转换则明确失败。上下文压缩只处理完整已结束回合，保留区维持原始内容块和签名，压缩失败不破坏原状态。

对外继续使用当前 SSE token/progress/error/done 等类型。reasoning、原生签名、凭据不出现在普通 token、会话展示、artifact_trace 或观测日志中；供协议重放的内部 checkpoint 按现有用户隔离和存储生命周期处理。

### 6. 集中请求预算与可控 fallback

定义配置、认证、权限、限流、超时/网络、服务端故障、能力不支持、上下文超限、结构校验、拒答/截断等分类。SDK 错误正文先脱敏，日志仅保留分类和安全字段。

由调用层拥有总 deadline 和次数预算，适配 SDK 重试关闭或计入同一预算；仅可恢复网络/限流/服务端错误重试，遵守 Retry-After 与取消。显式 fallback 不等于角色继承：在未向用户提交文本且未执行工具时，按配置和可移植历史切换；结构校验失败是否使用 fallback 由任务策略声明。已经提交文本或产生工具副作用后，禁止自动重跑整个 Agent。保留现有记忆任务快照，fallback 不触发重复经验检索。

OpenRouter 对硬性工具/schema 参数默认要求 `require_parameters=true`，路由 fallback 明确配置并进入证据元数据；如果不能返回实际上游，记录 unknown，不从 model slug 猜测。

### 7. 未来动态配置的扩展点

ConfigRepository 提供读取发布配置/快照接口，File/Env 为一期实现；SecretResolver 负责凭据，公开 DTO 仅含 schema、选项、配置状态与安全标识。模型实例不能读全局可变配置或任意外部请求 kwargs。

未来独立变更实现 DatabaseConfigRepository、密钥加密/授权、草稿校验与发布 API、前端表单、端点访问控制、配置引用删除约束及审计。编辑 → 测试 → 发布新版本只影响新工作流；本期不创建这些控制面表和接口。接口替换测试用内存仓库证明调用方无需随存储更换而修改。

### 8. 验证与证据

- 离线契约：配置冲突/继承环、强制能力、厂商 payload、stream tool args、thinking 往返、usage 缺失、认证失败、限流/取消、历史恢复、缓存隔离。
- 真实 smoke：三协议及 OpenRouter/DeepSeek/智谱每条路径验证文字、流式和工具往返；按声明增加 structured/vision/thinking。缺凭据记为未验证或跳过，不能记为通过。
- 业务回归：聊天、教学确认与恢复、并行产物、修改、memory worker 和压缩。在线用例保持 model_eval/integration 显式标记，默认测试不联网。
- manifest/benchmark 记录实际角色对应 provider、protocol、model、参数策略、配置和集成版本；可用时记录实际上游。保持 schema 2.0 兼容扩展并更新 allowlist，不记录 endpoint、密钥、凭据引用和正文，不把模型 ID/配置指纹随意添加为 Prometheus label。
- 保留现有 24 个 YAML 评估用例计数；新增协议契约放 pytest，新增真实 smoke 使用独立入口，不为凑协议覆盖而改变主评估集。

## Risks / Trade-offs

- [集成包文档与供应商当前能力不一致] → 锁定集成版本并以真实工具往返为准，能力表记录测试版本和日期。
- [签名丢失使第二轮失败] → 流合并、checkpoint、历史截取和压缩均使用含元数据的脱敏 fixture 验证。
- [快照增加存储量] → 只保存运行所需配置及角色引用；不存模型目录、客户端、正文或密钥。
- [旧环境变量依赖跨角色拼接] → 输出字段级迁移诊断，明确兼容收紧；上线前离线校验配置。
- [模型端点失效或密钥撤销] → 已固定任务明确失败，操作人员恢复原配置/凭据；不暗中切换供应商。
- [重试导致重复产物工具执行] → 仅请求级安全重试，不自动重放已执行工具的 Agent。
- [各模型输出效果不同] → 协议测试与教学效果评估分开报告，不能以 smoke 通过宣称效果无回归。

## Migration Plan

1. 配置与工厂：实现 schema、旧配置迁移、完整继承和 OpenAI 工厂；离线兼容门禁通过后进入入口迁移。
2. 入口与快照：新增可空字段，迁移模块级绑定及后台任务，验证跨重启/审批版本固定和旧记录首次接纳。
3. 原生协议：安装固定兼容依赖，接入 Anthropic/Gemini，验证消息/工具/结构化和取消语义。
4. 预设：完成 OpenRouter、DeepSeek、智谱及 custom 的规则与 smoke 矩阵；先保守兼容，再启用已验证 thinking 组合。
5. 发布验证：完成业务回归、证据元数据与脱敏 allowlist、Windows/Compose 示例、部署说明。发布前记录验证矩阵和未验证能力，未完成必需 smoke 不宣称全量支持。

上线先应用向后兼容的可空字段迁移，保留旧 env，以 openai_chat 验证既有流程，再按角色切换新连接。停止接收新任务并等待活动/待审批工作流处理完毕后做需降级的发布；仅退回旧配置文件时保留旧任务快照可恢复性。

回滚程序到不识别多协议历史的版本前，必须完成/取消新协议待审批工作流并停止相关后台任务；不能把其 checkpoint 交给旧版本继续执行。可空字段保留，不进行破坏性降表。业务提交先在 backend 子模块完成，再在根仓库提交配置文档与子模块指针。

## Research References

以下为 2026-09-19 调研来源，提供架构与兼容规则依据，不代表当前仓库已通过真实验证。

- [LangChain init_chat_model](https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model)：统一模型接口与集成包选择。
- [Pydantic AI Provider](https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pydantic_ai/providers/__init__.py)：Provider 与模型接口/能力描述分离。
- [Dify Anthropic 预设](https://github.com/langgenius/dify-official-plugins/blob/main/models/anthropic/provider/anthropic.yaml)、[OpenRouter 预设](https://github.com/langgenius/dify-official-plugins/blob/main/models/openrouter/provider/openrouter.yaml)：声明式 credential schema、自定义模型。
- [LiteLLM 转换层](https://github.com/BerriAI/litellm/blob/main/litellm/llms/base_llm/chat/transformation.py)：参数映射与流式/响应适配职责。
- [DeepSeek thinking](https://api-docs.deepseek.com/guides/thinking_mode/)：tools 场景 reasoning_content 回传，按实际模型版本验证。
- [Gemini thought signatures](https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures)、[LangChain Gemini](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai)：历史元数据和结构化方法。
- [Anthropic thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)：thinking 参数随模型代际变化。
- [OpenRouter 路由](https://openrouter.ai/docs/guides/routing/provider-selection)：require_parameters 与路由 fallback。
- [智谱兼容文档](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)：OpenAI 兼容端点及参数差异。

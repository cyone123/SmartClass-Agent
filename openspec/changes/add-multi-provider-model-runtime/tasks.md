## 1. 配置与模型工厂

本阶段建立 OpenAI 路径的兼容基础。对应 model-provider-configuration；完成阶段门禁后进入阶段 2。

- [x] 1.1 在 `app/core/model_access/` 定义协议、预设、连接、模型配置、角色绑定与快照 schema；以有效配置、互斥字段、未知版本和继承环测试验证解析行为。
- [x] 1.2 实现 File/Env ConfigRepository、`MODEL_CONFIG_PATH` 路径解析和 SecretResolver；验证 Windows 相对/绝对路径、缺失文件、缺失引用以及不输出密钥的诊断。
- [x] 1.3 实现旧 `MODEL/STRUCTURED/STRUCTURED_FAST/SMALL/MEMORY/CONTEXT_COMPRESSION/VIDEO_VISION` 配置映射；用现有 `test_llm.py` 加完整/部分身份配置用例验证兼容与字段级迁移提示。
- [x] 1.4 实现 YAML 优先、完整角色继承与必需/可选角色校验；覆盖混合新旧配置、不跨角色借凭据、禁用可选能力及原有回退顺序的测试。
- [x] 1.5 建立预设注册和能力/参数 schema，先提供 OpenAI/custom 基础与 legacy 兼容描述；验证未知能力、显式覆盖、协议不匹配和非法参数的处理。
- [x] 1.6 实现返回 BaseChatModel 的工厂与 openai_chat 适配器，并为 `llm.py` 保留兼容函数；验证原有 timeout、stream usage、thinking 行为及 bind_tools 接口。
- [x] 1.7 实现版本化配置指纹、公开 DTO 和无密钥的内部快照序列化；以 round-trip 和敏感字段探针测试证明 endpoint/credential references 只存在于允许的内部表示。
- [x] 1.8 实现缓存隔离和客户端生命周期；验证不同配置、streaming、tools、凭据代次不串用，应用关闭释放客户端且异步客户端不跨事件循环复用。
- [x] 1.9 完成阶段 1 门禁：运行配置/工厂及旧 llm 相关离线测试，验证默认启动无需新提供商密钥，并交付一份可离线加载的 YAML 示例。

## 2. 入口迁移与运行快照

依赖阶段 1。对应 durable-chat-runs、multi-protocol-model-runtime 的配置隔离要求；本阶段仍可仅用 OpenAI/fake 模型验证。

- [x] 2.1 为 AgentRun 新增可空模型配置快照字段与迁移，扩展服务内部 schema；验证旧行可读、新 run 在模型调用前持久化、外部聊天请求不能注入内部快照。
- [x] 2.2 在 graph state 与运行上下文引入工作流配置标识和快照传播；覆盖教学开始、补充要求、审批恢复、完成/取消、重启及新修改任务，验证同一 run 中识别出重启时从预先固定的快照封套选择新配置而不修改旧快照。
- [x] 2.3 实现旧 checkpoint/run 的一次性配置接纳；验证 legacy 标志、持久化失败时零模型请求，以及重启后不重新读取当前全局角色。
- [x] 2.4 将 `graph.py` 的模块级模型/工具绑定迁移为上下文解析，接入已有 ModelRuntime；运行主图动作、教学确认与 fallback 相关回归测试，确认审批节点保留。
- [x] 2.5 将 `agent.py` 的附件、产物生成/修改和建议调用迁移至角色工厂；验证并行产物共享工作流快照、不同任务模型/工具不串用及经验快照不重复检索。
- [x] 2.6 移除 `memory.py` 的全局工具绑定，扩展反思任务 snapshot schema 并传递 enqueue-time memory 配置；覆盖配置变更后执行、旧任务接纳和凭据缺失的 worker 测试。
- [x] 2.7 将压缩与 `video_transcribe.py` 视觉客户端接入角色工厂；验证独立视觉连接、禁用视觉不依赖其密钥、压缩模型失败保留原历史，并运行原 embedding/STT 回归确保独立实现不受影响。
- [x] 2.8 完成阶段 2 门禁：以两个配置版本模拟重启和审批恢复，验证旧工作流、并行分支、反思任务保持原模型身份，新工作流采用新版本；确认代码中没有遗留业务 ChatOpenAI 构造或模块级模型绑定。

## 3. Anthropic 与 Gemini 原生协议

依赖阶段 2。对应 multi-protocol-model-runtime 和 context-compression；优先用脱敏 fixture 完成契约，再执行真实 smoke。

- [ ] 3.1 选择并固定兼容的 LangChain/Anthropic/Google GenAI 集成版本；验证依赖解析、Windows import、现有 create_agent/middleware 接口和开发/容器安装方式。
- [ ] 3.2 实现 anthropic_messages 适配器与 Anthropic 基础预设；使用协议 fixture 验证 system 顺序、认证引用、流式、工具往返、结构化方法及模型适用的 thinking 参数映射。
- [ ] 3.3 实现 google_genai 适配器与 Gemini Developer API 预设；验证显式 Developer API 选择、文本/图片输入、流式、工具往返与结构化策略，宿主机 Vertex 环境变量不得改变目标。
- [ ] 3.4 统一角色必需能力和结构化策略校验，保留现有 action/记忆工具 schema；验证 required 字段、枚举/嵌套参数、非法 JSON、截断及不支持 forced tool 的组合不被无声降级。
- [ ] 3.5 统一展示文本提取和流增量处理，迁移主图、Agent、session 展示及视觉输出中的有损转换；验证 text/reasoning/tool 混合块、空文本结束块和原 SSE 契约，禁止内部字段泄漏到 token/artifact_trace。
- [ ] 3.6 保留工具调用标识、原生 reasoning/signature 元数据，修正历史过滤与截断边界；以三协议 fixture 验证 stream 合并 → checkpoint 序列化/恢复 → 第二轮请求，以及并行工具结果关联。
- [ ] 3.7 实现完整回合边界上的跨协议历史准备与 system/记忆边界处理；验证已完成历史可移植、未完成工具交换拒绝切换、不伪造签名且不将非可信记忆提升为指令。
- [ ] 3.8 调整压缩边界和摘要输入过滤；验证保留区原生元数据不变、工具交换不被切断、私有 reasoning/signature 不进入摘要提示、审批期间不压缩和失败保留历史。
- [ ] 3.9 统一错误分类与 SDK/运行时总重试预算；覆盖认证/能力错误、Retry-After、超时、取消、断流和结构校验 fallback，证明已输出文本或执行工具后不会重跑整个 Agent。
- [ ] 3.10 扩展 usage 归一化与错误脱敏；验证三协议的 input/output/total、usage 不可用、缓存/推理明细缺失，以及 exporter 关闭时正常工作和低基数 label 约束。
- [ ] 3.11 完成阶段 3 门禁：三协议离线契约全通过，执行显式标记的原生 Anthropic/Gemini 聊天、stream、工具闭环和已声明 structured/vision smoke；缺权限或凭据的项目记录未验证且保持本门禁未完成。

## 4. 提供商预设与兼容矩阵

依赖阶段 3。提供商仍使用明确协议，不根据模型名称改变连接。对应 model-provider-configuration 与 multi-protocol-model-runtime。

- [ ] 4.1 完成 OpenRouter 预设的端点、credential schema、reasoning/provider 参数和 require_parameters 策略；验证 anthropic/deepseek 前缀模型仍走选定协议，配置路由 fallback 与实际/未知上游记录正确。
- [ ] 4.2 完成 DeepSeek 预设并用固定集成版本验证 reasoning_content 完整往返，依据结果选择 ChatDeepSeek 或兼容实现；用工具多轮 fixture 验证保留 legacy thinking 关闭策略和仅开启受支持模式。
- [ ] 4.3 完成智谱国内标准 API 预设及 GLM 参数/能力规则；验证 endpoint、thinking/工具参数组合及模型 ID 自定义，禁止静默切换海外或 Coding 端点。
- [ ] 4.4 完成全部预设的公开配置 schema、可覆盖端点与模型 ID、多连接支持；验证能力来源/版本、声明与实测状态区分，以及自定义声明不能突破适配器硬限制。
- [ ] 4.5 建立与主评估 YAML 集分离的显式真实模型 smoke 入口和脱敏结果格式；验证逐 provider/model/protocol/capability 的通过、失败、未验证状态以及缺凭据不会计为通过。
- [ ] 4.6 完成阶段 4 门禁：执行 OpenRouter、DeepSeek、智谱的文本/stream/工具闭环 smoke 和各自声明的 structured/thinking/vision 检查；交付带日期、模型和依赖版本的兼容矩阵，不以另一条路由的结果替代验证。

## 5. 业务回归、证据与发布

依赖阶段 4。对应 evaluation-harness-integrity 以及全部跨能力验收；本期完成条件不包含未来配置管理页面/API。

- [ ] 5.1 修改 eval manifest 和 benchmark 模型摘要以使用实际配置快照/调用元数据；验证多角色 provider/protocol、thinking、配置/集成版本、fallback 与实际/未知上游记录，并移除硬编码 provider 推断。
- [ ] 5.2 更新报告 schema 2.0 兼容扩展与 benchmark 脱敏 allowlist；运行旧报告兼容、敏感字段剔除和 fail-closed 回归门禁测试，证明不同 thinking/路由条件不会当作同一配置合并。
- [ ] 5.3 补充跨层业务回归：聊天、教学要素/计划确认与恢复、三类产物 fan-out 和修改、记忆反思、压缩后继续；验证每类流程使用指定角色且不绕过审批、workspace 或 StorageService。
- [ ] 5.4 使用可替换内存配置仓库验证未来存储扩展接口，确认角色调用方不依赖 File/Env；交付未来 Database/Secret/管理 API 的接口说明与公开 DTO 示例，不创建管理 API 或前端页面。
- [ ] 5.5 更新根目录 env/YAML 示例、Compose 只读配置挂载和 README；验证 Windows 本地加载与容器配置解析，并写明部分 legacy 配置迁移、重启生效、凭据轮换和可选角色行为。
- [ ] 5.6 交付发布/回滚操作文档并演练快照兼容路径；验证旧记录迁移、新协议待审批任务不能由旧程序直接恢复，以及移除凭据时明确失败而非切换账号。
- [ ] 5.7 运行后端 `python -m pytest -q`、`python -m ruff check app tests`、`python -m ruff format --check app tests` 与 `python -m tests.evals.cli validate-suite --expected-count 24`，记录全部结果；在线/integration 验证显式单独运行，不将默认 pytest 当作真实协议证明。
- [ ] 5.8 汇总真实 smoke 和业务评估验收证据，保留 ERROR/FAILED、pass_rate/avg_score 与 deterministic/live/mixed 区分；仅在报告通过现有门禁时执行 baseline 晋升，未验证必需能力不得标记整个变更完成。

未来独立变更：数据库配置仓库、密钥加密与权限、草稿/测试/发布管理 API、前端设置页、端点访问控制、配置审计和引用删除策略。上述能力仅在本期设计中保留接口，不属于本任务清单。

# 阶段 1 / 阶段 2 验收记录

验收日期：2026-09-20。范围仅为 tasks.md 的 1.1–1.9、2.1–2.8；阶段 3–5 未实施、未验收。

## 门禁与证据

以下命令在 `backend/` 使用项目已有 `.venv/Scripts/python.exe` 执行。系统 Python 自动加载的 Qt pytest 插件存在 DLL 错误，因此使用项目虚拟环境。测试均为离线验证，不代表真实提供商兼容性或模型效果。

| 检查 | 结果 |
| --- | --- |
| `python -m pytest tests/test_model_access.py tests/test_llm.py tests/test_observability.py -q` | 阶段 1 门禁：53 passed |
| `python -m pytest tests/test_model_workflows.py -q` | 阶段 2 快照专项：13 passed |
| `python -m pytest -q` | 360 passed，8 deselected（默认排除的 model_eval/integration） |
| `python -m ruff check app tests` | 通过 |
| `python -m ruff format --check app tests` | 通过 |
| `python -m tests.evals.cli validate-suite --expected-count 24` | 24/24，用例集有效 |
| 根目录 `openspec validate add-multi-provider-model-runtime --strict` | 通过 |
| 业务入口静态检查 | ChatOpenAI 构造仅位于 `model_access/adapters/openai_chat.py`；业务模块无模块级模型实例或工具绑定 |

阶段 1 初次门禁在阶段 2 实施前通过（46 项）；修正混合配置兼容细节后复核扩大为 53 项。阶段 2 的完整回归包括原有审批、主图动作/fallback、附件/产物、经验快照复用、记忆 worker、压缩、embedding 和 STT 测试。

## 逐项证据定位

以下实现/测试路径相对 `backend/`。

| 任务 | 实现与验证 |
| --- | --- |
| 1.1 | `model_access/schemas.py`：协议、ProviderPreset、Connection、ModelProfile、RoleBinding、版本化快照；`test_model_access.py` 验证互斥字段、未知版本/协议、引用和继承环。 |
| 1.2 | `config_repository.py`、`secrets.py`：File/Env 仓库、仓库根相对路径和绝对路径、缺失文件/凭据诊断；测试验证错误不包含密钥值。 |
| 1.3 | `PREFIXES` 和 legacy 映射：完整身份保留、部分身份失败；`test_llm.py` 保留 thinking 行为；memory 优先显式 fast→structured→small→main，未配置 fast 的 small 回退不能抢占 structured。 |
| 1.4 | YAML 角色图先独立验证，然后合并未配置角色的 legacy 输入；完整身份继承；必需角色启动校验、禁用可选角色不解析凭据。混合配置测试保留 legacy timeout/thinking 策略。 |
| 1.5 | `registry.py` 和类型化预设/能力/参数 schema；能力未知、显式参数非法、协议不匹配拒绝；声明统一标记未实测，不能声明本适配器不支持的 reasoning round-trip。 |
| 1.6 | `factory.py`、`adapters/openai_chat.py`、`llm.py`：BaseChatModel 工厂和兼容函数；测试 timeout、stream usage、DeepSeek legacy thinking、bind_tools。 |
| 1.7 | 配置 SHA-256 指纹带 v1 前缀；round-trip 校验指纹；内部快照含无认证信息的 endpoint 和 env 引用，公开 DTO 排除两者，均不含密钥值。 |
| 1.8 | 工厂按快照、模型、streaming、凭据代次及事件循环隔离 HTTP 客户端，工具绑定不缓存；测试旋转凭据、独立绑定、关闭连接及跨循环隔离。应用 lifespan 管理初始化和关闭。 |
| 1.9 | 上述离线门禁、仅旧角色凭据启动测试；根目录 `model-config.example.yaml` 可无网络解析。 |
| 2.1 | `AgentRun.model_config_snapshot` 可空字段和 `v20260919_model_config_snapshot.py` 增量迁移；SQLite 验证旧行可读、接纳时已提交、公开请求不能注入/公开响应不返回快照。迁移 SQL 的重复执行契约有离线测试。 |
| 2.2 | `workflow.py` 的接纳封套同时固定 current/workflow；state 和 RunContext 传播工作流标识。真实 LangGraph checkpoint 测试覆盖澄清、两次审批、三分支、取消、同 run 重启及新修改工作流。 |
| 2.3 | `admission.py` 独立元数据 checkpoint 与 AgentRun 接纳持久化；一次性 legacy 标记；持久化失败前无附件/模型调用。重建运行图、接纳后执行前中断等测试证明恢复不改用当前全局配置。 |
| 2.4 | `graph.py` 按节点快照解析角色和工具，保留 ModelRuntime 与原审批拓扑；主图动作、stream 和 fallback 既有回归通过。 |
| 2.5 | `agent.py` 按任务构造附件/产物 Agent 和建议模型；不同并发任务模型/工具隔离。`test_memory_retrieval.py` 继续验证审批、并行产物复用经验快照及 fallback 不重复检索。 |
| 2.6 | 反思 snapshot v2（兼容 v1）携带入队配置；worker 处理旧任务先持久化接纳。SQLite worker 测试验证全局配置变化、重复接纳恢复和缺凭据明确失败。 |
| 2.7 | 压缩读取 checkpoint 的角色，初始化失败保留原历史；视觉按独立角色解析且可禁用。`test_video_attachment_flow.py`、`test_voice_input_flow.py` 和 embedding 配置测试保持独立路径行为。 |
| 2.8 | `test_model_workflows.py` 通过实际 checkpoint 序列化/恢复、重建图、SQLite 持久化和 fake 模型验证双版本身份；原配置快照不被修改，全部并行分支使用同一快照，后台任务固定入队身份，新工作流采用新版本。 |

## 部署与运行说明

- 本阶段只实现 `openai_chat`，预设为 `openai` / `custom` / `legacy`。原生 Anthropic/Gemini、其他预设和真实 smoke 留在阶段 3–5，不宣称可用。
- 已有数据库在部署本代码前执行 `python -m app.migrations.v20260919_model_config_snapshot`。迁移只添加可空 JSON 列，不回填猜测的历史配置。此次没有对现有部署数据库执行迁移。
- `MODEL_CONFIG_PATH` 相对仓库根解析，绝对 Windows 路径也支持。配置启动加载，修改后重启生效；凭据只写环境变量，YAML 只写 `env:NAME` 引用。离线解析不要求密钥，启动校验启用的必需角色。
- 完整 legacy 身份继续兼容；部分 model/key/endpoint 身份不再跨角色借用。仅 main/structured/small 原 SDK 的同角色 OpenAI 默认 endpoint 可补齐；memory/fast/compression/vision 专用身份要求明确 endpoint。禁用压缩/视觉不会要求专用凭据。
- 引用固定、秘密值执行时解析；凭据轮换隔离客户端代次。无法恢复历史密钥，原引用缺失时明确失败，不改用其他账号。
- 接纳元数据使用现有 checkpointer 的独立内部 thread（散列业务 thread_id）。这是为了在附件模型调用前持久化配置，同时不修改业务图的待审批任务。恢复使用 `Command(update=..., resume=...)` 把配置写回业务 state；不通过普通 `aupdate_state` 写快照，因为它会推进待执行节点。
- 已入库、尚未写入图状态的 legacy 接纳可从上一 run 的封套恢复。显式取消关闭配置工作流；进程中断仍遵循现有 stale run 失败规则。
- 未执行在线 smoke、模型评估或 benchmark baseline 晋升；没有把离线门禁当作真实模型能力证明。

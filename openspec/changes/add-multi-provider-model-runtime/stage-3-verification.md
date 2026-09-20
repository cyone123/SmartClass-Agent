# 阶段 3 验证记录

日期：2026-09-20。范围：任务 3.1–3.10。用户明确要求暂不完成在线 smoke；3.11 保持未勾选，阶段 3 的完整门禁未通过，阶段 4–5 未开始。

## 交付与契约证据

| 任务 | 实现与验证 |
|---|---|
| 3.1 | `requirements.txt` 固定 LangChain 1.2.15、core 1.2.28、OpenAI 集成 1.1.11 / SDK 2.28.0、Anthropic 集成 1.4.0 / SDK 0.93.0、Google 集成 4.2.1 / GenAI SDK 1.72.0、LangGraph 1.1.6。Windows `pip check`、开发安装 dry-run 通过。Linux/Python 3.12 容器实际安装同一 requirements-dev → requirements 链，`pip check` 与当时 48 项协议契约通过。生产 Dockerfile 继续安装同一 requirements.txt；没有启动或变更业务服务。 |
| 3.2 | `adapters/anthropic_messages.py` 使用原生 ChatAnthropic，密钥仅从引用解析；工厂持有 HTTP 客户端。HTTP fixture 覆盖 system 顺序、x-api-key、文本/图片、流式 thinking/signature、工具闭环、tool/native-schema 结构化、thinking budget 与 forced-tool 不兼容拒绝。 |
| 3.3 | `adapters/google_genai.py` 显式创建 `genai.Client(vertexai=False)`；在 Vertex 环境变量干扰下仍走 Developer API。绕过该固定集成版本遗漏底层 false 参数的行为，不修改进程环境。覆盖图片、流式、工具与结构化请求。 |
| 3.4 | 角色能力校验、显式 structured_method、工具 required/enum/嵌套字段及 Pydantic 结果校验。非法参数和截断不作为成功结果。Gemini 使用 `parameters_json_schema` 保留原 JSON schema，避免旧转换器丢弃 allOf/additionalProperties。已有教学动作与记忆工具定义未修改。 |
| 3.5 | `messages.display_text` 统一主图、Agent、会话历史、视觉、记忆与压缩的文本提取，只输出文本块；保留既有 SSE 事件类型。主图流式测试同时断言用户 token 不含 reasoning、内部 checkpoint 保留原块和工具交换。 |
| 3.6 | 三协议真实 SDK HTTP fixture：流合并 → JsonPlus checkpoint 编解码 → 下一轮工具结果请求。原始签名、工具 ID、并行结果关联保持；Google 修复原集成丢弃工具消息配套展示文本及原生 ID 的行为。动作历史保存 AIMessage 与 ToolMessage，不再重建为纯文本。 |
| 3.7 | 完整工具边界选择与跨协议历史准备；完成交换仅迁移可移植内容，未完成交换拒绝切换。system 顺序和非可信记忆提示保留。Gemini 3 缺原始签名时拒绝 SDK 注入的占位签名，不伪造签名。 |
| 3.8 | 压缩只能选择完整交换边界；保留区原对象不变，摘要输入只含展示文本，不含 thinking/signature。审批、未完成交换跳过；初始化、调用或空摘要失败保留原历史。需求收集的原生消息不做字符级截断。 |
| 3.9 | SDK 自动重试关闭（Google attempts=1）；请求级总次数上限 2、总 deadline 默认 60 秒，单次 timeout 不超过剩余预算。已有结构化/action fallback 共享预算且认证、权限、能力错误不 fallback。Retry-After、超时、取消、断流有契约测试；create_agent 工具副作用发生后模型失败只重试该请求，不重跑 Agent。兼容 core 1.2.28 子调用取消回调缺陷，向上恢复 CancelledError。 |
| 3.10 | 归一化三协议 input/output/total，缺 usage 标记不可用；缓存/推理计数仅在存在时保留。SDK 错误输出仅含分类，观测不保留错误正文。原可选 exporter 与低基数标签回归继续通过。 |

## 验证命令

从 backend 目录使用 `.venv/Scripts/python.exe` 执行：

- `-m pytest tests/test_native_model_protocols.py -q`：协议离线契约，HTTP 使用 MockTransport，不访问提供商。
- `-m pytest -q`：后端默认回归，明确排除 model_eval/integration。
- `-m ruff check app tests`、`-m ruff format --check app tests`。
- `-m tests.evals.cli validate-suite --expected-count 24`：原 24 个 YAML 用例全部有效，没有增加或替换主评估集。
- 根目录 `openspec validate add-multi-provider-model-runtime --strict`：通过。

最终结果：

| 检查 | 结果 |
|---|---|
| Windows 完整离线回归 | **420 passed, 18 deselected**（68.52 秒） |
| 最后一次三协议专项回归 | **60 passed**（13.58 秒） |
| Ruff check | 通过 |
| Ruff format --check | 162 files already formatted |
| 评估 YAML 校验 | 24 discovered / 24 loaded，全部有效 |
| OpenSpec strict validate | 通过 |
| 根仓库与 backend 的 git diff --check | 通过 |
| Linux/Python 3.12 安装与协议验证 | pip check 无冲突；当时 48 项契约通过 |

18 个 deselected 包含新加入的 10 个显式原生在线 smoke；默认 pytest 的成功不代表这些项目已验证。

容器使用本机已有 `smartclass-backend:local` 镜像、只读挂载 backend 源码、临时容器内安装 `requirements-dev.txt`，执行 `pip check` 和协议测试；退出自动删除容器。没有读取根目录 `.env`、调用真实模型或执行数据库迁移。此验证证明 Linux 安装/导入与协议契约，不代表完整生产镜像重建或业务部署。

## 在线验证状态

| 原生路径 | chat | stream | tools | structured | vision |
|---|---|---|---|---|---|
| Anthropic Messages | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 |
| Gemini Developer API | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 |

首次显式执行 `-m pytest -m model_eval tests/test_native_provider_smoke.py -q -rs` 得到 **10 skipped**，原因是缺少对应凭据或模型选择，未计为通过。后续用户要求在线 smoke 暂不完成，因此不继续请求在线访问。

未来验证时在本机配置 `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、`GEMINI_API_KEY`、`GEMINI_MODEL`，显式执行上述命令。测试使用预设官方端点，不借用 legacy OpenAI 角色的凭据或网关；不猜测模型 ID。全部必需在线项通过后才能勾选 3.11。测试成功仅证明请求契约，不证明教学质量；没有执行模型效果评估或 baseline 晋升。

## 兼容与限制

- 新增预设 `anthropic` / `gemini`，协议分别为 `anthropic_messages` / `google_genai`；custom 可显式选择三协议。能力仍是待实测声明，公开 DTO 保持 `verified=false`。
- `structured_method` 为 `tool_calling`（默认）或 `json_schema`；后者要求声明 structured 能力。工具强制选择要求 tool_choice 能力，不静默切换为无约束文本。
- thinking 非默认映射需要明确模式、预算及 reasoning_roundtrip 声明；Anthropic thinking 不支持强制工具选择，因此不能给必需 forced-tool 的角色配置该组合。没有宣称任意模型都支持同一 thinking 模式；真实可用性仍需逐模型验证。
- 新参数使用默认值时仍按旧 v1 规范计算指纹，已有阶段 1–2 快照可原样校验和恢复；非默认新参数进入指纹。未变更数据库 schema。
- 使用本版本原生历史的待审批任务不能交给不支持原生协议的旧程序继续执行。回滚前需按设计完成/取消相应工作流。

源码核对辅以官方参考：[LangChain Anthropic thinking](https://reference.langchain.com/python/langchain-anthropic/chat_models/ChatAnthropic/thinking)、[LangChain Google GenAI](https://reference.langchain.com/python/langchain-google-genai/chat_models/ChatGoogleGenerativeAI)。以上文档不是在线 smoke 证据；具体兼容修正由固定版本的 HTTP 契约测试覆盖。

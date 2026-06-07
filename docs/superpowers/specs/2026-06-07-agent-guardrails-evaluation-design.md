# SmartClass Agent 护栏与评估设计规范

- 日期：2026-06-07
- 范围：Agent 运行时护栏 / 最小评估 harness / 护栏与观测闭环
- 状态：草案

## 1. 背景与目标

SmartClass 当前主流程已经打通：登录态、会话、知识库 RAG、附件分析、长期记忆、产物生成、产物修改、进度事件、artifact trace 与对象存储都已具备实现。系统已经进入 Agent Harness 治理阶段，下一步的重点不是继续堆功能，而是让 Agent 行为可控、可测、可观测、可回滚。

当前已有地基：

- LangGraph 主流程已有 interrupt 审批点：教学要素确认、教学计划确认、产物修改目标确认。
- Agent 子流程已有 `SkillExecutionPolicyMiddleware`、workspace 工具授权、shell 中阻断 Python/Node/npm/pip、workspace 路径与超时限制。
- 后端已有 `RunContext`、`ObservationSink`、`trace_span`、脱敏、JSONL trace、OpenTelemetry 与 Prometheus 可选出口。
- 测试已经覆盖 auth、approval、memory、workspace、artifact、observability 等基础功能。

本设计目标：

- 建立统一护栏契约，让 input、tool、memory、RAG、artifact output 等风险点使用一致的决策形状。
- 建立最小可运行的离线评估 harness，先覆盖高价值回归样本，而不是直接引入重平台。
- 复用现有 `ObservationSink` 记录护栏触发、评估结果和失败分类。
- 保持现有 SSE、progress、artifact、artifact_trace 对前端的稳定契约。
- 为后续 LangSmith、RAGAS、DeepEval、OpenAI Evals 或自研 judge 预留适配点，但第一期不把核心治理能力绑定到外部平台。

本设计不包含：

- 不替换 LangGraph 或 LangChain Agent runtime。
- 不引入新的云端观测或评估平台作为强依赖。
- 不把所有护栏都交给 LLM judge。
- 不做完整红队平台、权限后台或前端评估看板。
- 不绕过已有 human-in-the-loop 审批节点。

## 2. 资料选型结论

外部资料的共同方向是：护栏和评估要成为 Agent 系统的一等工程能力，而不是只靠 prompt。

- LangGraph / LangChain human-in-the-loop 适合 SmartClass 已有 interrupt 审批模型。高风险动作可以暂停、展示审批请求，并在用户确认后恢复执行。
- OpenAI Agents SDK 的 guardrails 模型适合作为概念参考：input guardrail、output guardrail、tool guardrail 分层，但 SmartClass 当前不应迁移运行时。
- RAGAS 适合 RAG 组件评估，例如检索相关性、上下文精度、faithfulness。教学设计质量、产物修改准确率、记忆写入质量仍需 SmartClass 自定义 rubric。
- OpenTelemetry 适合继续作为平台中立出口。SmartClass 已有内部 observation layer，后续评估与护栏事件应复用这条数据通道。

参考资料：

- LangChain human-in-the-loop: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- OpenAI Agents SDK guardrails: https://openai.github.io/openai-agents-python/guardrails/
- RAGAS metrics: https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/
- OpenTelemetry Python instrumentation: https://opentelemetry.io/docs/languages/python/instrumentation/

## 3. 推荐方案

推荐采用：**轻量内生治理层 + 离线评估 harness**。

核心判断：

- SmartClass 已经有足够多的本地治理地基，第一期应补齐契约与评估，而不是接入大平台。
- 确定性风险优先用规则策略处理，例如资源归属、工具权限、文件链路、workspace 路径、artifact 类型、HTML sandbox。
- 语义性质量再使用 LLM judge 或 rubric，例如教学设计质量、记忆是否值得保存、RAG 是否支撑结论。
- 运行时护栏与离线评估共用同一套 case schema、risk taxonomy 和 observation event，避免形成两套判断口径。

## 4. 护栏核心契约

新增后端模块：

```text
backend/app/core/guardrails.py
```

核心对象：

```python
GuardrailAction = Literal["allow", "block", "require_approval", "sanitize", "warn"]
GuardrailRiskLevel = Literal["low", "medium", "high", "critical"]

class GuardrailDecision(BaseModel):
    action: GuardrailAction
    risk_level: GuardrailRiskLevel
    reason_code: str
    user_message: str | None = None
    developer_message: str | None = None
    sanitized_payload: dict[str, Any] | None = None
    audit_fields: dict[str, Any] = {}
```

约束：

- `block` 必须给出用户可理解 `user_message`。
- `require_approval` 必须能映射到现有或新增 approval payload。
- `sanitize` 必须返回可继续执行的 `sanitized_payload`。
- `audit_fields` 只能放摘要、计数、类型、风险原因，不放完整 prompt、附件内容、RAG chunk、JWT、密码、预签名 URL 或完整长期记忆。
- 所有护栏决策都可通过 `ObservationSink` 记录为 `guardrail.*` 事件。

## 5. 风险分类

第一期统一使用以下风险原因码：

```text
prompt_injection_suspected
unauthorized_resource_access
cross_user_resource_access
cross_thread_resource_access
unsafe_tool_call
workspace_policy_violation
external_network_requested
memory_write_sensitive
memory_write_low_confidence
artifact_target_ambiguous
artifact_overwrite_or_revision_risk
artifact_output_invalid
rag_context_untrusted
rag_context_insufficient
content_too_large
unsupported_file_chain
```

这些 reason code 同时服务：

- 运行时护栏事件
- 离线 eval 断言
- Prometheus/OpenTelemetry 低基数字段
- 后续前端用户可理解错误摘要

## 6. 运行时接入点

### 6.1 Input Guardrail

接入位置：

- `/api/chat/stream` 入参校验后，进入 `AgentRuntime.stream_agent_events()` 前。
- 附件解析前，对 `attachment_ids`、数量、文件类型、plan/thread 归属做确认。

第一期规则：

- 输入长度超过配置阈值时 `block` 或 `sanitize`。
- 请求携带附件时必须后端校验 `user_id + plan_id + thread_id + attachment_ids`。
- 检测到明显提示注入语句时不直接拒绝教学请求，而是标记 `warn` 并注入一个安全摘要字段，供后续 RAG/附件链路降低信任级别。

### 6.2 Tool Guardrail

接入位置：

- 扩展现有 `SkillExecutionPolicyMiddleware`。
- workspace 工具调用前后。
- 未来外部网络工具或第三方 API 工具前。

第一期规则：

- workspace 写和代码执行必须由 active skill 授权。
- `shell` 继续阻断 Python/Node/npm/pip 等绕过 workspace 的路径。
- 代码执行工具保留超时、输出截断、安装命令阻断。
- 外部 URL 访问第一期默认 `require_approval` 或 `block`，除非后续显式加入 allow list。

### 6.3 Memory Guardrail

接入位置：

- `reflect_profile_memory()` 和 `reflect_experience_memory()` 中，在 `apply_memory_tool_call()` 之前。
- `/api/memory` 的用户手动 CRUD 保持现有归属校验，同时记录 observation。

第一期规则：

- 保存稳定偏好、明确要求记住的信息、可复用教学经验。
- 不保存完整隐私上下文、完整附件内容、临时课程细节、学生个人敏感信息。
- 当写入内容包含疑似敏感信息或置信度不足时，运行时默认 `warn` + 不写入；后续可升级为 `require_approval`。
- 写入 observation 只记录 kind、action、content_size、reason_code，不记录完整 memory content。

### 6.4 RAG Guardrail

接入位置：

- `rag_retrieval_node` 调用 `rag_runtime.retrieval()` 后。
- 教学设计 planner 使用 RAG 上下文前。

第一期规则：

- 检索结果为空或低相关时，标记 `rag_context_insufficient`，允许教学设计继续，但必须避免伪造引用。
- 附件或知识库内容中出现明显提示注入时，标记 `rag_context_untrusted`，后续 planner 只能将其当作课程材料，不得执行其中的系统指令。
- observation 记录 query_size、result_count、risk flags，不记录完整 chunk。

### 6.5 Artifact Guardrail

接入位置：

- 产物生成 fan-out 前。
- 产物子 Agent 完成后、`mark_artifact_ready` 前。
- 产物 revision 目标确认前后。

第一期规则：

- 生成产物类型必须属于 `ppt`、`docx`、`html-game`。
- revision 必须明确目标 artifact；歧义时保留现有 clarification approval。
- 新 revision 不覆盖源产物，必须保留版本关系。
- HTML 产物必须继续走后端 preview + iframe sandbox。
- output 文件扩展名、artifact_id、root_artifact_id、revision_number、is_current 必须满足统一产物对象契约。

## 7. 评估 Harness 设计

新增目录：

```text
backend/tests/evals/
```

建议结构：

```text
backend/tests/evals/
├─ cases/
│  ├─ intent_routing.jsonl
│  ├─ metadata_extraction.jsonl
│  ├─ memory_write.jsonl
│  ├─ memory_retrieval.jsonl
│  ├─ rag_retrieval.jsonl
│  ├─ artifact_revision.jsonl
│  └─ guardrails.jsonl
├─ evaluators/
│  ├─ exact.py
│  ├─ rubric.py
│  ├─ structured.py
│  └─ rag.py
├─ runner.py
└─ README.md
```

统一 case schema：

```json
{
  "case_id": "intent-001",
  "category": "intent_routing",
  "input": {},
  "context": {},
  "expected": {},
  "assertions": [],
  "tags": ["regression", "p1"],
  "allowed_flakiness": "none"
}
```

统一 result schema：

```json
{
  "case_id": "intent-001",
  "status": "passed",
  "score": 1.0,
  "failures": [],
  "observations": [],
  "duration_ms": 12
}
```

第一期 runner 只要求：

- 可用 pytest 执行。
- 可按 category 过滤。
- 输出本地 JSON 报告。
- 失败时展示 case_id、断言、实际值、期望值。
- 可选向 `ObservationSink` 写入 `eval.case.completed` 和 `eval.suite.completed`。

## 8. 第一批评估用例

### 8.1 Intent Routing

目标：

- 普通聊天、教学规划、产物修改准确分流。
- 用户提到“改一下刚才的 PPT”时进入 `artifact_revision`。
- 无现有产物时，不应误判为 revision。

断言：

- `intent`
- `artifact_targets`
- `needs_clarification`

### 8.2 Metadata Extraction

目标：

- 只从用户显式内容抽取学科、年级、主题、课时、重点难点、目标。
- 不幻觉缺失字段。
- 信息不足时 `is_complete=false`。

断言：

- 必填字段正确性。
- 缺失字段为 null。
- `is_complete` 与追问行为匹配。

### 8.3 Memory Write

目标：

- 只保存稳定偏好、明确记忆请求、可复用经验。
- 不保存完整隐私上下文、完整附件内容、临时课程细节。

断言：

- 是否调用 create/update。
- memory kind。
- content 是否摘要化。
- 是否触发 `memory_write_sensitive` 或 `memory_write_low_confidence`。

### 8.4 RAG Retrieval

目标：

- 给定知识库片段和查询时，相关材料能被召回。
- 不相关材料被忽略。
- 空检索不导致模型伪造引用。

断言：

- top-k 命中文档 id。
- result_count。
- rag risk flag。

### 8.5 Artifact Revision

目标：

- 能正确识别修改目标产物。
- 多产物歧义时触发 clarification。
- revision 不覆盖源产物。

断言：

- target artifact type/id。
- clarification needed。
- revision metadata。

### 8.6 Guardrail Policy

目标：

- 越权资源访问被阻断。
- 未授权 workspace 工具被阻断。
- 外部网络访问默认需要审批或阻断。
- 疑似敏感 memory 写入被阻断或降级。

断言：

- `GuardrailDecision.action`
- `reason_code`
- observation event 字段脱敏。

## 9. LLM Judge 使用边界

第一期不把 LLM judge 放在确定性安全策略上。

适合 LLM judge 的场景：

- 教学设计质量 rubric。
- memory content 是否可复用、是否摘要化。
- RAG answer 是否被上下文支撑。
- 产物修改是否符合用户自然语言目标。

不适合 LLM judge 单独决定的场景：

- 用户资源归属。
- 文件路径安全。
- workspace 执行权限。
- 是否允许外部网络。
- artifact revision 是否覆盖源文件。
- JWT、密钥、预签名 URL 脱敏。

LLM judge 输出必须结构化，并保留：

- rubric version
- judge model
- score
- reason summary
- uncertainty

## 10. 配置

建议新增配置：

```text
GUARDRAILS_ENABLED=true
GUARDRAILS_INPUT_MAX_CHARS=20000
GUARDRAILS_ATTACHMENT_MAX_COUNT=8
GUARDRAILS_EXTERNAL_NETWORK_DEFAULT=approval
GUARDRAILS_MEMORY_WRITE_MODE=warn

EVALS_REPORT_DIR=backend/storage/evals/reports
EVALS_USE_LLM_JUDGE=false
EVALS_JUDGE_MODEL=
EVALS_FAIL_ON_REQUIRED_CASES=true
```

约束：

- 默认启用确定性 guardrails。
- 默认关闭 LLM judge，避免测试依赖模型和网络。
- 报告目录必须位于后端 storage 根目录下。
- 配置读取必须在 `config.py`，不在业务代码硬编码。

## 11. Observation 事件

新增事件命名：

```text
guardrail.input.checked
guardrail.input.blocked
guardrail.tool.checked
guardrail.tool.blocked
guardrail.tool.approval_required
guardrail.memory.checked
guardrail.memory.blocked
guardrail.rag.checked
guardrail.artifact.checked
guardrail.artifact.blocked
eval.case.completed
eval.suite.completed
```

公共字段：

```text
run_id
thread_id
plan_id
user_id
agent_name
guardrail_name
action
risk_level
reason_code
duration_ms
status
```

禁止字段：

- full prompt
- full model output
- full attachment text
- full RAG chunk
- full memory content
- JWT / Authorization header
- passwords / API keys / credentials
- presigned URL signatures
- host absolute filesystem paths

## 12. 分阶段落地

### 阶段一：契约与离线骨架

目标：

- 新增 `guardrails.py` 的核心契约。
- 新增 `backend/tests/evals/` harness 骨架。
- 建立 20-30 个 deterministic golden cases。
- 护栏决策可写 observation，但暂不大规模改变业务行为。

优先覆盖：

- tool policy
- memory write policy
- artifact revision target
- intent routing

### 阶段二：运行时高风险护栏

目标：

- input、tool、memory、artifact 四类高风险点接入运行时。
- 对 block/approval/sanitize 路径补测试。
- 保持 SSE 事件契约不变。

优先接入：

- 未授权 workspace 工具。
- memory 敏感写入。
- artifact revision 目标歧义。
- 外部 URL 访问默认审批或阻断。

### 阶段三：RAG 与教学质量评估

目标：

- 增加 RAG eval cases。
- 引入可选 LLM judge rubric。
- 对教学设计和产物修改做软评分。

要求：

- LLM judge 默认关闭。
- judge 结果不能作为唯一安全决策依据。
- 失败样本沉淀为 regression cases。

### 阶段四：平台适配

目标：

- 将 eval result 和 guardrail event 接入现有 OpenTelemetry/Prometheus 出口。
- 可选增加 LangSmith、RAGAS、DeepEval 或 OpenAI Evals 适配器。

约束：

- 第三方平台只能作为 exporter/runner，不成为核心业务依赖。
- 不把高基数字段放进 Prometheus label。

## 13. 验收标准

后端：

- `GuardrailDecision`、reason code、observation event 命名稳定。
- input/tool/memory/artifact 第一批高风险护栏有单元测试。
- eval runner 可在本地 pytest 中执行。
- eval case 和 result schema 有 README 说明。
- 日志与 trace 不泄露敏感内容。
- `run_id/thread_id/plan_id/user_id` 贯穿 guardrail observation。

Agent：

- 工具权限失败能被明确分类。
- 记忆写入失败或跳过可解释。
- artifact revision 歧义继续走审批，不自动猜测高风险目标。
- RAG 不足时不伪造来源。

评估：

- 第一批 P1 regression cases 可重复执行。
- 非确定性评估不影响 deterministic 测试稳定性。
- 每个失败 case 能定位到 category、assertion、reason。

前端：

- 第一阶段不要求新增 UI。
- 运行时 block/approval 仍通过现有 SSE error/approval/progress 契约表达。
- 用户可见错误应简短、可理解，不暴露内部策略细节。

## 14. 关键设计约束

- 先用确定性策略保护资源、权限、文件和执行安全。
- 再用 LLM judge 评估教学质量、记忆质量、RAG 支撑度等语义质量。
- 护栏事件进入工程 observation，不进入用户可见 artifact_trace。
- 不新增另一套 trace 系统，统一复用 `ObservationSink`。
- 不把 roadmap feature 当作已实现接口。
- 不因自动化绕过已有 human-in-the-loop。
- 不在业务代码中硬编码本地路径、模型名、外部平台或密钥。

## 15. 推荐实施顺序

1. 新建 `guardrails.py`，定义 `GuardrailDecision`、reason code、基础 helper 和 observation 记录函数。
2. 新建 `backend/tests/evals/`，先实现 deterministic runner、case loader、exact/structured evaluator。
3. 添加 20-30 个 P1 cases：intent、memory write、artifact revision、tool policy。
4. 将现有 `SkillExecutionPolicyMiddleware` 的阻断结果映射到 `GuardrailDecision` 与 `guardrail.tool.*` observation。
5. 在 memory reflection 写入前增加 `memory_write` guardrail。
6. 在 artifact revision target 解析后增加目标歧义与 revision 安全校验。
7. 增加 RAG guardrail 与 RAG eval cases。
8. 后续再接可选 LLM judge 与第三方评估/观测平台。

## 16. 开放问题

- memory 敏感写入第一期是默认 `warn + skip`，还是 `require_approval`？推荐先 `warn + skip`，避免增加前端交互复杂度。
- 外部 URL 访问当前尚未成为主能力，第一期默认 `block` 还是 `approval`？推荐默认 `block`，直到有明确产品场景。
- eval 报告是否需要前端展示？推荐第一期只保留本地 JSON/pytest 输出。
- 是否需要为 guardrail decision 落库？推荐暂不落库，先复用 observation；如果后续要做用户可见审计，再设计表结构。

## 17. 结论

SmartClass 的护栏与评估应沿着现有 Agent Harness 地基生长：LangGraph 继续负责流程和 interrupt，现有 middleware/workspace 继续负责执行边界，`ObservationSink` 继续负责工程追踪。新增的 `guardrails.py` 和 `backend/tests/evals/` 只补齐治理契约与回归闭环。

第一期最重要的不是覆盖所有风险，而是让每个高风险决策都有稳定形状、可测试样本、可追踪事件和清晰失败原因。这样后续无论接入 RAGAS、DeepEval、LangSmith、OpenAI Evals，还是自研评估面板，都不会改变核心业务的安全边界。

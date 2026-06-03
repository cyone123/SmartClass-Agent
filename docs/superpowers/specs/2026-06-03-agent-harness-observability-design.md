# SmartClass Agent Harness 可观测性地基设计规范

- 日期：2026-06-03
- 范围：Agent 核心链路观测性 / 结构化日志 / 工程 trace / metrics / token usage / 错误分类
- 状态：草案

## 1. 背景与目标

SmartClass 当前已经具备 `run_id`、SSE progress、artifact trace、LangGraph 主流程、RAG、workspace 工具执行和产物生成链路。但工程诊断平面仍不统一：

- `print()` 分散在 Agent、Graph、Memory、Skills、视频分析等模块中
- 用户可见 `artifact_trace` 和工程排障 trace 没有明确边界
- Graph 节点、RAG、工具、workspace、模型调用的耗时与失败分类不统一
- 模型 token 消耗尚未形成稳定记录入口
- 后续 guardrails、evaluation harness 和自动排障缺少统一数据来源

第一期目标不是接入完整 APM 平台，也不是重构前端事件协议，而是在后端建立一个轻量、可扩展、可安全落地的 Agent Harness 可观测性地基。

本次设计目标：

- 建立统一 `RunContext`，贯穿 chat stream、LangGraph、RAG、artifact 子 Agent 和 workspace 工具
- 建立统一 `ObservationSink`，支持结构化日志、可选 JSONL trace 和 metrics 事件
- 记录 Agent 核心链路的耗时、状态、错误分类、输入输出大小和模型 token 消耗
- 替换核心链路中的高风险 `print()`，避免泄露完整 prompt、附件、RAG 内容、密钥或预签名 URL
- 保持当前 SSE 事件契约不变，不把工程 trace 暴露给前端
- 为后续 DB sink、OpenTelemetry、Prometheus、LangSmith 类平台和 evaluation harness 预留接口

本次不包含：

- 新增数据库表
- 接入 Prometheus、OpenTelemetry、LangSmith 或第三方观测平台
- 前端埋点与浏览器错误采集
- OnlyOffice、auth、memory API 等后端全链路覆盖
- 将工程 trace 展示给用户
- 大规模重构 LangGraph 节点结构

## 2. 方案选择

### 2.1 采用方案

推荐采用：**Harness Context 路线**。

新增后端观测性模块，例如：

- `backend/app/core/observability.py`

核心由三类对象组成：

- `RunContext`：保存运行关联字段
- `ObservationEvent`：保存日志、span、metric 的统一事件形状
- `ObservationSink`：保存事件出口，默认写入 Python logging，可选写入本地 JSONL trace

### 2.2 不采用的方案

#### 方案 A：薄封装日志

只提供 `log_event()`、`trace_span()`、`record_metric()`，逐步替换 `print()`。

- 优点：最快，侵入小
- 缺点：运行上下文、token usage、工具调用和 Graph 节点不容易形成统一协议

#### 方案 B：落库 trace

新增 `agent_run_events` 或 `agent_spans` 表。

- 优点：后续查询方便
- 缺点：第一期需要迁移、索引、查询 API 和清理策略，容易偏离“观测性地基”目标

#### 方案 C：中间件优先

优先在 LangChain Agent middleware 层包住模型调用和工具调用。

- 优点：能快速抓到模型和工具行为
- 缺点：Graph 节点、RAG、artifact、workspace 等业务 span 仍会分散

### 2.3 结论

第一期采用 **RunContext + ObservationSink + trace_span** 的轻量 Harness Context 方案，不落库，默认结构化日志，可选 JSONL trace。

## 3. 核心契约

### 3.1 RunContext

`RunContext` 是工程观测性中的稳定关联上下文。

建议字段：

```python
@dataclass(frozen=True)
class RunContext:
    run_id: str
    thread_id: str | None = None
    plan_id: int | None = None
    user_id: str | None = None
    agent_name: str | None = None
```

约束：

- `run_id` 必须来自 `/api/chat/stream` 创建的同一个值
- `thread_id`、`plan_id`、`user_id` 只能来自后端认证与服务层结果，不能信任前端传入用户字段
- `agent_name` 用于区分 `main_graph`、`attachment_agent`、`artifact_ppt_agent`、`artifact_docx_agent`、`artifact_html_agent` 等执行角色
- 子任务可以派生上下文，但不能丢失父级 `run_id`

### 3.2 ObservationEvent

建议事件形状：

```python
ObservationKind = Literal["log", "span", "metric"]
ObservationStatus = Literal["running", "success", "failed"]

@dataclass(frozen=True)
class ObservationEvent:
    event: str
    kind: ObservationKind
    context: RunContext
    status: ObservationStatus | None = None
    duration_ms: int | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
```

约束：

- `event` 使用点号命名，例如 `chat.stream.request`、`graph.node.intent_router_node`
- `fields` 必须先经过脱敏与截断
- 事件输出不能依赖前端 SSE 是否连接成功
- 工程 trace 与用户可见 `artifact_trace` 分离

### 3.3 ObservationSink

建议接口：

```python
class ObservationSink(Protocol):
    def emit(self, event: ObservationEvent) -> None:
        ...
```

默认 sink：

- `LoggingObservationSink`：写 Python `logging`，使用结构化 `extra`
- `JsonlTraceSink`：可选开启，写入本地 JSONL 文件
- `CompositeObservationSink`：组合多个 sink
- `NoopObservationSink`：观测性关闭时使用

## 4. 配置项

配置必须从配置层或环境变量读取。

建议新增：

```text
OBSERVABILITY_ENABLED=true
OBSERVABILITY_LOG_LEVEL=info
OBSERVABILITY_TRACE_JSONL_ENABLED=false
OBSERVABILITY_TRACE_JSONL_DIR=<backend/storage/observability/traces>
OBSERVABILITY_MAX_FIELD_CHARS=1000
OBSERVABILITY_MAX_JSONL_BYTES_PER_EVENT=20000
```

约束：

- 默认不写 JSONL trace，避免本地磁盘意外增长
- JSONL 目录必须在后端 storage 根目录下，不能写到项目外不受控路径
- 日志级别只影响 logging sink，不应关闭 error 类事件的工程记录

## 5. 数据流设计

### 5.1 Chat Stream

`backend/app/api/chat.py` 当前在 `event_stream()` 中创建 `run_id` 并发送 `metadata` SSE。

第一期改造：

1. 创建 `run_id`
2. 构造 `RunContext(run_id, thread_id, plan_id, user_id)`
3. 发送现有 `metadata` SSE，契约不变
4. 向观测性 sink 写入 `chat.stream.request`
5. 调用 `AgentRuntime.stream_agent_events()` 时传入 `run_context` 或可从 `run_id` 派生的配置
6. 流结束写入 `chat.stream.completed`
7. 异常写入 `chat.stream.failed`，SSE 仍返回用户可理解 `error`

### 5.2 AgentRuntime

`backend/app/core/agent.py` 当前负责主图执行、附件分析、artifact 子 Agent、artifact trace 和 progress reporter。

第一期改造：

- `stream_agent_events()` 接收或构造 `RunContext`
- `get_thread_config()` 增加 `run_context` 和 `observation_sink`
- Graph 输入不再 `print()` 完整状态，只记录输入字段摘要和大小
- `artifact_trace` 继续只服务前端用户可见轨迹
- 工程事件通过 `ObservationSink` 输出，不进入 SSE

### 5.3 LangGraph 节点

Graph 节点仍保留现有 `emit_progress()`，因为它是用户可见流程卡片协议。

第一期在核心节点增加工程 span：

- `graph.node.intent_router_node`
- `graph.node.metadata_structer_node`
- `graph.node.rag_retrieval_node`
- `graph.node.teaching_design_planner`
- `graph.node.artifact_revision_router_node`
- `graph.node.artifact_fan_in_node`

节点 span 记录：

- `node_name`
- `status`
- `duration_ms`
- `input_size`
- `output_size`
- `error_category`
- 与业务相关的安全摘要字段，例如 `intent`、`rag_result_count`、`selected_artifact_type`

### 5.4 RAG

RAG 检索第一期记录：

- `event="rag.retrieve"`
- `plan_id`
- `query_size`
- `result_count`
- `duration_ms`
- `status`
- `error_category`

不记录：

- 完整 query
- 完整 chunk
- 完整知识库文件内容

### 5.5 Artifact 生成与修改

artifact 子 Agent 第一期记录：

- `artifact.generate`
- `artifact.revise`
- `artifact.mark_ready`
- `artifact.mark_failed`

字段：

- `artifact_type`
- `artifact_id`
- `source_artifact_id`
- `revision_number`
- `workspace_backend`
- `duration_ms`
- `status`
- `error_category`

产物用户可见事件仍走现有 SSE `artifact` 和 `artifact_trace`。

### 5.6 Workspace 工具执行

workspace 执行第一期记录：

- `workspace.code_execution`
- `tool.invoke`

字段：

- `tool_name`
- `language`
- `entrypoint`
- `workspace_backend`
- `exit_code`
- `timed_out`
- `output_file_count`
- `stdout_size`
- `stderr_size`
- `duration_ms`
- `status`
- `error_category`

约束：

- 不记录完整 stdout/stderr
- 不记录 host 绝对路径
- 不记录 sandbox credential
- 继续继承 workspace 路径穿越、依赖安装命令阻断、输出截断和超时策略

## 6. 日志设计

### 6.1 结构化字段

日志字段建议统一为：

```python
{
    "event": "rag.retrieve",
    "kind": "span",
    "run_id": "...",
    "thread_id": "...",
    "plan_id": 1,
    "user_id": "2",
    "agent_name": "main_graph",
    "status": "success",
    "duration_ms": 123,
    "error_category": None,
    "input_size": 240,
    "output_size": 1180,
}
```

### 6.2 替换 print 的优先级

第一期优先替换：

- `backend/app/core/agent.py` 中完整 graph input、AIMessage、ToolMessage、异常输出
- `backend/app/core/graph.py` 中 structured output latency 打印
- `backend/app/core/memory.py` 中 reflection / selection skipped 打印
- `backend/app/core/skills.py` 中 skill activation 和 resource loading 打印中属于核心 Agent 工具链的部分

视频分析链路第一期不做深改，但如果附件分析触发视频处理，应至少能记录 `attachment_analysis` 的顶层状态事件。

## 7. JSONL Trace 设计

JSONL trace 用于本地工程排障，不默认开启。

建议路径：

```text
backend/storage/observability/traces/YYYY-MM-DD.jsonl
```

每行是一个已经脱敏和截断的 `ObservationEvent`。

约束：

- JSONL 文件不包含完整 prompt、完整附件、完整 RAG chunk、完整模型输出
- 单事件大小受 `OBSERVABILITY_MAX_JSONL_BYTES_PER_EVENT` 限制
- 写入失败不能影响主业务流程，只能写 warning 日志
- 后续可以基于同一 sink 接口替换为 DB、OpenTelemetry 或其他平台

## 8. Metrics 与 Token Usage

### 8.1 Metric 事件

第一期 metrics 仍通过 `ObservationSink` 输出，不单独接 Prometheus。

建议事件：

- `llm.call`
- `llm.structured_output`
- `rag.retrieve`
- `tool.invoke`
- `workspace.code_execution`
- `artifact.generate`
- `artifact.revise`

### 8.2 Token 消耗

模型调用必须尽量记录 token usage。

建议字段：

```python
{
    "event": "llm.call",
    "kind": "metric",
    "model": "model-name",
    "status": "success",
    "duration_ms": 1420,
    "input_tokens": 1234,
    "output_tokens": 380,
    "total_tokens": 1614,
    "token_usage_available": True,
    "input_size": 6200,
    "output_size": 900,
}
```

token 来源优先级：

1. LangChain message 的 `usage_metadata`
2. OpenAI 兼容响应中的 `response_metadata.token_usage`
3. 若模型提供方未返回 usage，则记录 `token_usage_available=false`

约束：

- 不在本地估算 token，避免把近似值误当事实
- `llm.call` 可记录模型名、耗时、token、tool call 数量和工具名列表
- 不记录完整 prompt
- 不记录完整 tool args
- 不记录完整模型输出

### 8.3 Agent 模型调用覆盖点

`backend/app/core/agent.py` 当前已有 `LoggingMiddleware.wrap_model_call()` 能接触 `ModelRequest` 与 `ModelResponse`。

第一期建议将其演进为 `LLMObservationMiddleware`：

- 记录 `agent_name`
- 记录模型调用耗时
- 记录 token usage
- 记录 tool call count 与 tool names
- 保留脱敏后的 message count、input_size、output_size

### 8.4 结构化输出覆盖点

`backend/app/core/graph.py` 当前 `_invoke_structured_runnable()` 已经记录 structured output latency，但使用 `print()`。

第一期改造为：

- `trace_span("llm.structured_output")`
- 记录 `schema_name`
- 记录 `schema_phase`
- 记录 `schema_invocation_index`
- 记录 `model`
- 记录 `duration_ms`
- 记录 token usage
- 记录是否 fallback
- 失败时记录 `error_category="model_error"`

## 9. 错误分类

第一期错误分类作为工程字段，不改变业务异常模型。

建议枚举：

```python
ErrorCategory = Literal[
    "model_error",
    "tool_error",
    "workspace_error",
    "rag_error",
    "artifact_error",
    "memory_error",
    "storage_error",
    "permission_error",
    "validation_error",
    "timeout",
    "unknown",
]
```

建议新增：

```python
def categorize_error(exc: BaseException) -> ErrorCategory:
    ...
```

识别规则：

- `StorageError` 使用 `storage_error`，并保留其内部 `category` 到 `storage_error_category`
- `WorkspaceValidationError` 使用 `validation_error` 或 `permission_error`
- `WorkspaceExecutionError` 使用 `workspace_error`，超时使用 `timeout`
- RAG 调用点异常使用 `rag_error`
- artifact 服务调用点异常使用 `artifact_error`
- LLM/structured output 调用点异常使用 `model_error`
- 无法识别时使用 `unknown`

SSE `error` 继续返回用户可理解摘要，工程日志记录：

- `error_category`
- `error_type`
- `error_message`

`error_message` 必须脱敏和截断。

## 10. 安全与脱敏

所有 sink 写出前必须经过统一清洗函数，例如：

```python
def sanitize_observation_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    ...
```

必须处理：

- JWT / Bearer token
- API key / secret key / password
- MinIO credential
- Daytona credential
- OpenAI 兼容模型 key
- 预签名 URL 查询参数
- 超长文本
- Windows / host 绝对路径
- 完整附件内容
- 完整 RAG chunk
- 完整 prompt 与完整模型输出

允许记录：

- 内容大小
- 短 preview
- hash 或稳定 id
- 工具名
- schema 名
- artifact id
- storage backend
- workspace backend

## 11. 实现边界

### 11.1 新增模块

建议新增：

- `backend/app/core/observability.py`

可包含：

- `RunContext`
- `ObservationEvent`
- `ObservationSink`
- `NoopObservationSink`
- `LoggingObservationSink`
- `JsonlTraceSink`
- `CompositeObservationSink`
- `get_observation_sink()`
- `trace_span()`
- `record_metric()`
- `log_observation()`
- `extract_token_usage()`
- `categorize_error()`
- `sanitize_observation_fields()`

### 11.2 配置模块

建议调整：

- `backend/app/config.py`

新增 observability 配置读取函数。

### 11.3 AgentRuntime

建议调整：

- `backend/app/core/agent.py`

改造点：

- `get_thread_config()` 携带 `run_context` 与 `observation_sink`
- `stream_agent_events()` 记录 chat / graph run 级别事件
- `LoggingMiddleware` 演进为 `LLMObservationMiddleware`
- artifact 生成与修改记录工程 span
- workspace tool 结果摘要进入工程观测事件

### 11.4 LangGraph

建议调整：

- `backend/app/core/graph.py`

改造点：

- `_invoke_structured_runnable()` 记录 `llm.structured_output`
- 核心节点用 `trace_span()` 包裹
- RAG 检索记录 `rag.retrieve`
- 保留现有 `emit_progress()`

### 11.5 Workspace

建议调整：

- `backend/app/core/workspace.py`

改造点：

- 记录 `workspace.code_execution`
- 记录 `tool.invoke`
- 继续使用已有路径、超时、输出截断和 Daytona 安全策略

## 12. 测试策略

第一期至少新增或更新以下测试：

### 12.1 脱敏与截断

`test_observability_sanitizes_sensitive_fields`

验证：

- JWT 被脱敏
- API key 被脱敏
- password / secret 字段被脱敏
- 预签名 URL 查询参数被脱敏
- 长文本被截断

### 12.2 Span 成功与失败

`test_trace_span_emits_success_and_failed_events`

验证：

- 成功 span 记录 `duration_ms` 和 `status=success`
- 失败 span 记录 `duration_ms`、`status=failed`、`error_category`
- 异常继续向外抛出，不被观测性层吞掉

### 12.3 Token Usage

`test_llm_usage_metadata_is_recorded_when_available`

验证：

- 能从 `usage_metadata` 提取 input/output/total token
- 能从 `response_metadata.token_usage` 提取 token
- 无 usage 时记录 `token_usage_available=false`

### 12.4 Run Context

`test_chat_stream_passes_run_context_to_agent_runtime`

验证：

- `run_id`、`thread_id`、`plan_id`、`user_id` 进入 `RunContext`
- SSE `metadata` 仍按原契约发送

### 12.5 Structured Output

`test_structured_output_print_replaced_by_observation_event`

验证：

- structured output latency 走 observation sink
- 事件包含 schema、model、duration、status
- 不依赖 `print()`

### 12.6 Workspace Execution

`test_workspace_execution_records_observation_event`

验证：

- workspace 执行事件包含 backend、language、entrypoint、duration、status
- stdout/stderr 只记录大小或截断摘要
- 失败时包含 error category

## 13. 验收标准

第一期完成后应满足：

- 核心 Agent 链路不再依赖 `print()` 做工程诊断
- 每次 `/api/chat/stream` 都有统一 `run_id` 工程上下文
- Graph 核心节点、RAG、LLM structured output、Agent LLM 调用、workspace 执行、artifact 生成或修改都有结构化事件
- 模型调用在可获取时记录 token 消耗
- token 不可获取时显式记录 `token_usage_available=false`
- 日志和 JSONL trace 不泄露完整 prompt、附件、RAG chunk、JWT、密钥或预签名 URL
- 现有 SSE 事件契约保持不变
- 观测性 sink 写入失败不影响主业务流程
- 测试覆盖脱敏、span、token usage、run context、structured output 和 workspace execution

## 14. 后续演进

第一期完成后，可按以下方向继续：

1. **Guardrails Harness**
   - input guardrail
   - tool guardrail
   - output guardrail
   - tripwire 中止与错误分类

2. **Evaluation Harness**
   - golden eval cases
   - route / metadata / RAG / artifact / revision 评测集
   - 评测结果关联 `run_id` 与工程 trace

3. **持久化与外部平台**
   - DB sink
   - OpenTelemetry exporter
   - Prometheus metrics
   - LangSmith 或同类平台适配

4. **前端与用户可见诊断**
   - 前端 SSE 消费错误埋点
   - 用户可见失败原因摘要
   - 管理端运行摘要页面

## 15. 风险与注意事项

1. **工程 trace 不能混入前端 SSE 协议。** 用户可见 progress / artifact trace 与工程 trace 必须分离。
2. **脱敏必须在 sink 写出前完成。** 不能依赖调用点都记得脱敏。
3. **token usage 只能记录模型真实返回值。** 不做本地估算，避免误导成本分析。
4. **不要一次性包完所有后端链路。** 第一阶段聚焦 Agent 核心链路，降低改动风险。
5. **JSONL trace 默认关闭。** 避免本地磁盘增长和隐私内容长期留存。
6. **观测性层不能改变业务控制流。** sink 写入失败最多写 warning，不能阻断聊天或产物生成。
7. **Windows 路径要谨慎处理。** 不要把 host 绝对路径暴露给 sandbox、日志或 agent-visible output。

## 16. 结论

第一期 Agent Harness 可观测性方案定为：

- 不落库
- 不接外部平台
- 保持 SSE 契约不变
- 新增 `RunContext`
- 新增 `ObservationSink`
- 默认结构化日志
- 可选本地 JSONL trace
- 记录核心链路 span、metrics、错误分类和模型 token 消耗
- 统一脱敏与截断

这是一套低侵入但可持续演进的观测性地基。它不会把 SmartClass 变成观测平台项目，但能让后续 guardrails、evaluation harness、自动排障和可靠 Agent 迭代拥有稳定的数据来源。

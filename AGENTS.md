# AGENTS.md

## 项目概览

SmartClass Agent：面向教师的多模态教学智能体。后端用 LangGraph 编排「记忆加载 → 意图识别 → 教学要素抽取 → RAG 检索 → 教学设计 → 产物生成/修改」主流程，产出 PPTX / DOCX / 单文件 HTML 互动内容；前端是 Vue 3 三栏工作台，通过 SSE 消费流式事件。

**本仓库是 super-repo，`backend/`、`frontend/`、`landing-page/` 都是 git 子模块。** 改动子模块内代码要先在子模块目录里提交，再回根仓库提交指针更新；`git status` 在根目录只会显示子模块的 dirty 状态。克隆用 `git clone --recurse-submodules`，已克隆则 `git submodule update --init --recursive`。

## 常用命令

### 后端（`backend/`）

```bash
python run_server.py                  # 启动 FastAPI，默认 127.0.0.1:8000
python run_server.py --reload         # 热重载

python -m pytest -q                   # 默认测试集
python -m pytest tests/test_auth_flow.py -q          # 单文件
python -m pytest tests/test_auth_flow.py::test_x -q  # 单用例
python -m pytest -k storage -q                       # 按名字筛选
python -m pytest -m model_eval        # 需要真实模型的用例（默认被排除）
python -m pytest -m integration       # 需要数据库/对象存储的用例（默认被排除）

python -m ruff check app tests
python -m ruff format --check app tests   # 后端 CI 会跑，提交前请确认
```

`pyproject.toml` 里 `addopts = -m "not model_eval and not integration"`，所以**默认 `pytest` 跑不到模型/外部依赖用例**，要显式加 `-m`。依赖分三层：`requirements.txt`（运行）、`requirements-dev.txt`（含 pytest/ruff）、`requirements-benchmark.txt`（含 locust）。

### 评估与压测（`backend/` 目录下执行）

```bash
python -m tests.evals.cli validate-suite --expected-count 24   # 离线严格校验，CI 强制门禁
python -m tests.evals.cli list-categories
python -m tests.evals.cli run --category intent_recognition --local-docker-db
python -m tests.evals.cli run --case-id intent_basic_chat_001 --local-docker-db --verbose
python -m tests.evals.check_regression --report tests/evals/results/<report>.json
python -m tests.evals.cli promote-baseline --report <report>.json --baseline-id <id>

python -m tests.benchmarks.context_compression_ab --turns 30 50 100 --repeats 3
python -m tests.benchmarks.artifact_generation --phase smoke --local-docker-services --model-env ../.env
python -m locust -f tests/benchmarks/sse_load.py --headless --host http://127.0.0.1:8000 -u 1 -r 1 --run-time 30s
```

`--local-docker-db` 表示「Python 在宿主机、PostgreSQL 在本仓库 Compose 里」，会从根目录 `.env.docker` 读库配置并强制走 `127.0.0.1`；容器内运行不要加。

### 前端（`frontend/`）

```bash
npm install
npm run dev      # 5173，/api 代理到 127.0.0.1:8000
npm run build    # 唯一的 CI 门禁，没有 lint / 单测
```

`vite.config.js` 把 `/web-apps`、`/sdkjs`、`/coauthoring`、`/cache`、`/savefile` 代理到硬编码的 OnlyOffice 主机，改动预览链路时注意这一点。

### Docker

```bash
cp .env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

服务：frontend / backend / postgres(pgvector) / redis / minio / minio-init / onlyoffice / otel-collector / prometheus / grafana。

## 架构要点

### 配置与模型角色

`.env` 位于**仓库根目录**，不在 `backend/`（`app/config.py` 与 `app/core/llm.py` 都是 `parents[2] / ".env"`）。模板是根目录的 `.env.local.example` / `.env.docker.example`。

`app/core/llm.py` 按用途拆了多个 OpenAI 兼容模型角色，各自独立配 `MODEL/API_KEY/BASE_URL`：主对话（`MODEL`，streaming）、结构化输出（`STRUCTED_*`）、小模型（`SMALL_*`）、结构化快模型（`STRUCTURED_FAST_*`）、记忆（`MEMORY_*`）、上下文压缩（`CONTEXT_COMPRESSION_*`）、语音（`STT_*`）、视频视觉（`VIDEO_VISION_*`）、向量（`EMBEDDINGS_*`）。未配置的角色会按固定链路回退到上一级。

DeepSeek 兼容接口在结构化输出（tool calling）时会被自动关闭 thinking；`MODEL_THINKING_MODE` 只接受 `enabled` / `disabled`，且会被写进 benchmark 报告元数据，不同 thinking 状态的结果不能合并统计。

### LangGraph 主流程（`app/core/graph.py`，约 60KB）

节点在文件末尾 `StateGraph` 处集中装配，读代码从那里入手最快：

```
START → profile_memory_load_node → intent_router_node
  ├─ 普通聊天: normal_chat_node
  ├─ 教学规划: metadata_structer_node → 补充/确认 → RAG → teaching_design_planner
  │            → 教学计划确认 → ppt/docx/html_game_generate_node
  └─ 产物修改: artifact_revision_router_node → 澄清/准备 → ppt/docx/html_game_revision_node
产物节点 → artifact_fan_in_node → END
```

三种产物节点并行 fan-out、`artifact_fan_in_node` 汇聚。审批用 LangGraph `interrupt()` 实现（教学要素确认、教学计划确认、产物修改目标澄清），恢复靠 checkpointer；**新增自动化能力不要绕过这些确认节点**。长期记忆反思已移出图，由后台 worker 处理。图状态定义在 `app/core/state.py` 的 `TeachingAssistantState`。

### Agent Runtime（`app/core/agent.py`，约 97KB）

`AgentRuntime` 是产物子 Agent 的执行器。核心 middleware 负责 skill 提示与授权、动态 system prompt、工具重试和 LLM 观测；任务级 Profile/Experience 在 Agent 启动时一次性注入，不在每轮模型调用中检索。Skill 定义在 `backend/skills/<name>/SKILL.md`，由 `app/core/skills.py` 的 `SkillRegistry` 加载。

**Skill 的文档风格借鉴 Anthropic progressive disclosure，但运行时是 OpenAI 兼容接口，不是 Anthropic SDK。**

### Workspace 沙箱（`app/core/workspace.py`）

产物生成在隔离 workspace 中进行，工具只有 5 个：`list_workspace_files`、`read_workspace_file`、`write_workspace_file`、`replace_workspace_text`、`run_workspace_code`。已有约束——路径穿越防护、执行超时、输出截断、禁止安装依赖、shell 里拦截 python/node/npm/pip——**新增执行能力必须继承这些约束，不能绕过 workspace 工具走 shell**。

执行后端由 `WORKSPACE_EXECUTION_BACKEND` 切换：`local`（子进程）或 `daytona`（远程沙箱，默认全网络阻断）。

### 三条文件链路（`app/models/file.py`）

`knowledge_files`（知识库 / RAG）、`attachment_files`（会话上下文分析）、`artifact_files`（Agent 产出的用户可见产物）是**三条独立链路，不能混用**。新增多模态能力先明确归属哪条。

产物迭代通过 revision 链维护：`parent_artifact_id`、`root_artifact_id`、`revision_number`、`is_current`。

### 存储抽象（`app/core/storage.py`）

所有文件读写必须走 `StorageService`（`LocalStorageBackend` / `MinioStorageBackend`），用稳定的 `storage_key` 定位。数据库里的 `storage_path` 只为兼容历史本地文件，**新代码不要再散落 `Path(storage_path)` 直接读写**。对象存储不保证有本地路径，需要本地文件时用 `materialize_temp_file`。预签名与下载策略集中在存储层，不要下沉到业务逻辑。

### 长期记忆（`app/core/memory.py`）

按用户命名空间隔离：`("users", user_id, "profile")` 与 `("users", user_id, "experiences")`。Profile 每次会话加载一次；Experience 由业务调用按语义检索，并以任务级快照在规划、审批恢复和并行产物间共享，不再使用固定检索节点。会话结束后只登记反思任务，由单个后台 `MemoryReflectionWorker` 异步写入；进程崩溃时运行中的任务可失败，不使用租约。记忆必须摘要化、最小化，显式用户指令优先；用户可通过 `/api/memory` CRUD。

### SSE 事件契约（`app/api/chat.py`）

持久运行接口先由 `/api/chat/runs` 创建后台任务，再通过 `/api/chat/runs/{run_id}/events` 从 Redis 顺序读取/续传 SSE；任务执行不依赖客户端连接，断线重连不会取消任务。PostgreSQL 保存运行状态，Redis 保存流式事件与短期输出，Redis 不可用时服务 readiness 失败。兼容接口 `/api/chat/stream` 仍保留。

事件类型为 `metadata`、`token`、`progress`、`artifact`、`artifact_trace`、`approval`、`suggestions`、`error`、`done`。新增类型要同步修改后端白名单、Redis 事件层和前端消费逻辑。

### 可观测性（`app/core/observability.py`）

`RunContext` 贯穿 `run_id`/`thread_id`/`plan_id`/`user_id`/`agent_name`；用 `trace_span()`、`record_metric()`、`log_observation()`、`observe_llm_call()` 发事件，出口是 `ObservationSink`（结构化日志 + 可选 JSONL trace + OTel span + Prometheus）。OTel 与 Prometheus 默认关闭且必须保持可选，不把第三方平台写死进业务代码。

两条硬约束：
- **不记录**完整 prompt / completion / 附件正文 / RAG chunk / 记忆正文 / JWT / Authorization / 预签名签名 / 对象 key / 宿主机路径。
- **Prometheus label 必须低基数**，`run_id`、`thread_id`、`user_id`、文件名、对象 key、URL 一律不能做 label。

### 评估与 benchmark 证据

`backend/tests/evals/` 是评估 harness：YAML 用例在 `cases/`（当前 24 个，分类以 YAML 的 `category` 字段为准而非目录名），evaluator 在 `evaluators/`，runner 汇总成 `EvalReport`（schema 2.0）写入 `results/`（已 gitignore）。

回归门禁 `check_regression` 是 **fail-closed**：缺分类、有 ERROR、通过率低于 `regression_thresholds.yaml`、或非 Schema 2.0，一律失败。

**只有通过门禁的报告才能 `promote-baseline` 晋升为 `docs/benchmarks/baselines/<id>/` 下的可提交证据**，且证据只允许聚合指标和非敏感元数据（详见 `docs/benchmarks/README.md` 的脱敏 allowlist）。同名 baseline 默认不可覆盖，需显式 `--replace`。`docs/benchmarks/raw/` 是 gitignore 的本地原始数据。

指标口径：`avg_score` 不能替代 `pass_rate` 对外表述；`ERROR` 与 `FAILED` 分开统计；确定性用例（`context_compression`）不能包装成模型效果，混合运行必须标记 `run_mode: mixed`。

## 平台与工程约束

- **Windows 优先**：`run_server.py`、`app/main.py`、`tests/evals/cli.py` 都显式切到 `SelectorEventLoop`（psycopg 在 Windows 上需要）。路径、shell、OnlyOffice 接入都要保持 Windows 兼容，别默认 Linux-only 写法。
- `tests/conftest.py` 强制 `STORAGE_BACKEND=local` 并清空代理环境变量，避免测试读到本机 `.env` 的 MinIO/代理配置；同时用测试占位值填充全部模型 env。
- Ruff：`line-length = 120`，规则集 `E/F/W/I`，忽略 `E501`；`tests/**` 放开 `E402`（评估 CLI 需要在 import 前设环境变量）。
- 所有模型、存储、JWT、外部服务配置必须来自配置层，不在业务代码里硬编码本机路径、外部地址或密钥。
- 提交信息用 Conventional Commits。

## 变更提案流程

`openspec/` 采用 spec-driven 流程：`openspec/specs/<capability>/spec.md` 是当前能力规范，`openspec/changes/archive/<date>-<slug>/` 保存已归档提案（proposal / design / tasks / specs）。较大的架构变更（沙箱、对象存储、可观测性、上下文压缩、测量系统等）都留有对应记录，改动同类能力前值得先读一遍对应 spec。

## 延伸文档

- `README.md` — 面向用户的安装与功能说明
- `backend/tests/evals/README.md` — 评估系统详细说明
- `docs/benchmarks/README.md` — benchmark 证据规范与脱敏要求
- `docs/observability/` — OTel Collector 与 Prometheus 本地接入示例

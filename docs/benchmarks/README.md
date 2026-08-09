# SmartClass Benchmark 证据规范

本目录只保存可公开、可复现、经过脱敏的实验汇总。原始评估结果保存在
`backend/tests/evals/results/`，默认被 Git 忽略，不得直接作为简历证据提交。

## 目录约定

```text
docs/benchmarks/
├─ README.md
└─ baselines/
   └─ <baseline-id>/
      ├─ manifest.yaml
      ├─ summary.json
      └─ report.md
```

- `manifest.yaml`：实验命令、代码版本、数据集指纹、样本量、指标定义和限制。
- `summary.json`：只包含总体与分类聚合指标。
- `report.md`：供人工审阅和面试展示的简短报告。

## 生成流程

在 `backend` 目录执行：

```powershell
python -m tests.evals.cli validate-suite --expected-count 24
python -m tests.evals.cli run
python -m tests.evals.check_regression --report tests/evals/results/<report>.json
python -m tests.evals.cli promote-baseline `
  --report tests/evals/results/<report>.json `
  --baseline-id <baseline-id>
```

普通 `run` 只生成本地原始报告。只有显式执行 `promote-baseline`，且报告通过回归门禁后，
才会生成可提交证据。Baseline ID 默认不可覆盖；确需替换时必须显式传入 `--replace`。

上下文压缩 A/B 使用独立的生产入口 benchmark：

```powershell
python -m tests.benchmarks.context_compression_ab `
  --turns 30 50 100 `
  --repeats 3 `
  --trigger-tokens 6000 `
  --keep-recent-turns 6 `
  --promote-baseline context-compression-ab-YYYY-MM-DD
```

该脚本使用固定合成长对话，A 组关闭压缩，B 组调用真实压缩模型；晋升时只写入聚合结果，
原始逐次报告仍保存在 `backend/tests/evals/results/`。

## 阶段 4：非 RAG SSE 压测

`backend/tests/benchmarks/sse_load.py` 使用 Locust 访问认证后的 `/api/chat/stream`，
固定普通聊天提示词，不进入教学设计、RAG 或产物分支。每次请求必须收到
`metadata`、至少一个 `token` 和最终 `done`；不完整或出现 `error` 的流计为失败。
脚本同时记录完整 SSE 请求耗时和 TTFT（首个 token 延迟），认证请求标记为 `[setup]`，
不混入正式指标。

建议先以单用户 smoke，再按阶梯并发执行；`--csv` 是 Locust 原始汇总，
`SMARTCLASS_BENCHMARK_OUTPUT` 保存脱敏 JSON 汇总：

```powershell
cd backend
$env:PYTHONUTF8 = "1"
$env:SMARTCLASS_BENCHMARK_TOKEN = "<short-lived-token>"
$env:SMARTCLASS_BENCHMARK_OUTPUT = "..\\docs\\benchmarks\\raw\\sse-smoke.json"
python -m locust -f tests/benchmarks/sse_load.py `
  --headless --host http://127.0.0.1:8000 `
  -u 1 -r 1 --run-time 30s --csv ..\\docs\\benchmarks\\raw\\sse-smoke
```

正式压测应至少拆为 Mock LLM 与真实 LLM 两种模式。Mock 模式用于测服务自身容量，
真实 LLM 模式用于测用户可见 TTFT；两者不得合并统计。报告至少包含并发数、持续时间、
请求数、完整率、错误率、TTFT p50/p95、完整请求耗时 p50/p95，以及运行环境和模型信息。
该实验不测 RAG 检索质量或 RAG 延迟。若需要定位 SSE `error` 原因，脚本会在聚合 JSON
中写入脱敏后的 `error_reasons`（分类、错误类型和短消息），并在 Locust failure CSV
中追加低基数分类；不持久化原始错误正文、凭据或 URL 查询参数。

未通过稳定性门禁的阶段 4 探索性运行放在 `docs/benchmarks/runs/`，不放入
`baselines/`，也不能直接用于简历。只有完成多轮重复、错误归因和资源采样后，
才可将聚合报告晋升为正式 baseline。

本次正式矩阵使用 `tests/benchmarks/run_sse_matrix.ps1`，每个窗口由
`resource_sampler.ps1` 以 1 秒间隔采集后端进程工作集、私有内存、CPU、线程和句柄，
并由 `aggregate_sse_matrix.py` 汇总 Mock/真实模型对照结果。续跑指定轮次时使用
`-StartRound`，避免覆盖已落盘窗口：

```powershell
pwsh -File tests/benchmarks/run_sse_matrix.ps1 `
  -BackendPid <pid> -Mode mock `
  -OutputRoot ../docs/benchmarks/raw/sse-formal-mock-YYYYMMDD `
  -DurationSeconds 300 -Rounds 3

python tests/benchmarks/aggregate_sse_matrix.py `
  --input-root mock=../docs/benchmarks/raw/sse-formal-mock-YYYYMMDD `
  --input-root live=../docs/benchmarks/raw/sse-formal-deepseek-YYYYMMDD `
  --output-dir ../docs/benchmarks/runs/sse-chat-load-formal-YYYY-MM-DD `
  --rounds 3
```

若真实模型窗口出现上游超时，报告保留失败请求与脱敏后的 `error_reasons`，稳定性门禁应为
`FAIL`，简历只能按实际成功率和错误归因描述，不能宣称全量 100% 通过。

产物生成实验使用 5 个固定跨学科合成场景，每个场景重复 2 次，并在真实生产链路中并行生成
PPTX、DOCX 与单文件 HTML，共 30 个正式样本：

```powershell
python -m tests.benchmarks.artifact_generation `
  --phase formal `
  --local-docker-services `
  --model-env ../.env `
  --model-profile main `
  --timeout-seconds 600 `
  --promote-baseline artifact-generation-YYYY-MM-DD
```

通过 DeepSeek 官方 API 执行工具型 Agent 时，可保持模型默认思考模式；正式基线会把该状态记为
`thinking_mode: null`。只有在目标兼容接口明确要求时，才显式设置：

```powershell
$env:MODEL_THINKING_MODE = "disabled"
```

显式设置会写入实验报告的模型元数据；不得把默认、thinking-disabled 与 thinking-enabled 结果
合并统计。

首次接入模型或调整生成链路后，建议先执行 `smoke`（3 个样本）和 `pilot`（6 个样本），再运行
`formal`；无论是否执行预跑，只有正式实验自身的证据门禁与产品阈值全部通过，才可晋升 baseline。
当前不依赖 OnlyOffice：PPTX/DOCX 使用 ZIP、XML、OOXML schema 和解析器校验，HTML 使用
JavaScript 语法及交互结构校验；报告必须明确这不包含 Office 视觉渲染、溢出检查或人工教学审阅。

## 必填实验信息

每份正式 baseline 必须能回答：

- 使用哪个 Git commit、哪一版用例集与数据集 SHA-256。
- 运行模式是 `deterministic`、`smoke` 还是 `model-eval`。
- 模型 provider、模型名和非敏感采样参数；确定性实验应留空。
- OS、Python 版本、关键功能开关和执行命令。
- 样本量、通过率、错误率、平均分及分类指标。
- 实验限制，例如 Fake Model 结果不能代表真实模型延迟或质量。

## 指标口径

- `pass_rate = passed / total_cases`
- `error_rate = error / total_cases`
- `avg_score` 为单用例 score 的算术平均值
- 分类指标只统计该分类的用例
- `ERROR` 与 `FAILED` 分开统计；必需分类存在任何 `ERROR` 时回归门禁失败

平均分不能替代通过率。示例：一个分类平均分为 0.90，但只通过一半用例时，
其通过率仍为 50%，不得按“90% 通过”对外表述。

## 隐私与提交限制

可提交文件不得包含：

- prompt、completion、记忆正文、附件正文或 RAG chunk；
- JWT、Authorization、API Key、预签名 URL 参数；
- 对象 key、用户名目录、宿主机绝对路径；
- 完整且无边界的异常消息；
- 单个用户、thread、plan 或 run 的敏感上下文。

正式报告只允许使用聚合字段 allowlist。发现敏感内容时，必须删除该 baseline、修复脱敏测试后重新晋升。

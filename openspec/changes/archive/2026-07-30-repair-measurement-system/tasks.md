## 1. 固化评估契约与审计现有用例

- [x] 1.1 在 `backend/tests/evals/suite_validation.py` 实现递归用例发现、重复 `case_id` 检查、类别检查、断言支持检查和字段契约检查，并返回结构化诊断
- [x] 1.2 在 `backend/tests/evals/test_suite_validation.py` 增加当前 24 个 YAML 全量发现、坏 YAML、重复 ID、未知断言、非法字段和目录名不参与分类语义的测试
- [x] 1.3 在 `backend/tests/evals/cli.py` 增加 `validate-suite` 命令，支持 `--expected-count`，任何 warning 级遗漏均转为非零退出
- [x] 1.4 运行静态审计并生成当前用例的 category、断言类型、字段引用清单，作为 YAML 迁移依据

## 2. 修复断言分发与 evaluator 输出

- [x] 2.1 修改 `backend/app/core/evaluation.py`，让 `AssertionType` 与当前保留的断言集合一致，并增加报告 Schema 所需的分类指标与运行元数据模型
- [x] 2.2 修改 `backend/tests/evals/evaluators/base.py`，实现显式断言注册表和 `UnsupportedAssertionError`，移除 LLM Judge 异常时固定返回 0.5 的降级
- [x] 2.3 在 `backend/tests/evals/evaluators/base.py` 实现并测试 `route_match`、`contains`、`not_contains`、`count_check`、`encoding_check` 和统一的 Judge 断言语义
- [x] 2.4 修改 `backend/tests/evals/evaluators/memory_evaluator.py`，定义并输出稳定的 profile/experience 加载、写入、更新、数量和隐私检查字段
- [x] 2.5 修改 `backend/tests/evals/evaluators/extraction_evaluator.py`，统一使用 `teaching_metadata` 输出契约，并按期望字段检查准确性、完整性和未知值处理
- [x] 2.6 修改 `backend/tests/evals/evaluators/context_compression_evaluator.py`，在结果中显式标记 Fake Model 和 `deterministic` 运行模式
- [x] 2.7 扩充 `backend/tests/evals/evaluators/test_assertions.py`、`test_memory_evaluator.py` 和 `test_extraction_evaluator.py`，覆盖每种保留断言的通过、失败和错误路径

## 3. 迁移并严格校验 24 个 YAML 用例

- [x] 3.1 修改 `backend/tests/evals/cases/memory/*.yaml`，将断言字段对齐 Memory evaluator 输出，并移除或迁移 `semantic_match`、`count_check`、`encoding_check` 等未落地语义
- [x] 3.2 修改 `backend/tests/evals/cases/extraction/*.yaml`，将 `extracted_elements` 等旧字段统一为 `teaching_metadata`，明确“未知学科/年级”的无幻觉判定
- [x] 3.3 检查 `backend/tests/evals/cases/intent/*.yaml` 与 `context_compression/*.yaml` 的字段契约和运行模式标记
- [x] 3.4 修改 `backend/tests/evals/runners/eval_runner.py`，始终递归加载后按 `EvalCase.category` 过滤；任何解析失败都终止 suite
- [x] 3.5 更新 `backend/tests/evals/runners/test_eval_runner.py`，纳入 `context_compression` evaluator，并验证 24/24 用例可加载及各分类数量正确

## 4. 统一报告 Schema 与回归门禁

- [x] 4.1 在 `backend/tests/evals/manifest.py` 实现 Git commit、数据集 SHA-256 指纹、OS/Python、关键开关和非敏感模型摘要采集
- [x] 4.2 修改 `backend/tests/evals/runners/eval_runner.py`，生成带 `schema_version`、`run_mode`、`pass_rate`、`error_rate`、`category_metrics` 和 manifest 的新报告
- [x] 4.3 为旧 JSON 增加只读 legacy 兼容，禁止 legacy 报告被自动当作新回归基线
- [x] 4.4 修改 `backend/tests/evals/check_regression.py`，从 `backend/tests/evals/regression_thresholds.yaml` 读取必需类别和 pass-rate 阈值，并让缺失类别、任何 ERROR、阈值下降均返回非零
- [x] 4.5 在 `backend/tests/evals/fixtures/reports/` 增加通过、阈值下降、缺失类别、运行错误和 legacy 五类固定报告
- [x] 4.6 扩充回归脚本与 runner 测试，验证平均分和通过率不会混用，且统计公式在空集合和错误结果下正确

## 5. 建立可提交的 benchmark 证据链

- [x] 5.1 在 `backend/tests/evals/reporting.py` 实现字段 allowlist、脱敏汇总和 Markdown 报告生成，复用现有 observability 脱敏规则
- [x] 5.2 在 `backend/tests/evals/cli.py` 增加 `promote-baseline --report <path> --baseline-id <id>`，生成 `manifest.yaml`、`summary.json` 和 `report.md`
- [x] 5.3 保留 `backend/tests/evals/results/.gitignore` 对原始 JSON 的忽略，并新增测试确保普通 run 不写入 `docs/benchmarks/`
- [x] 5.4 新建 `docs/benchmarks/README.md`，规定实验目录、命名、环境、命令、样本量、指标定义、限制和原始数据留存方式
- [x] 5.5 在 `backend/tests/evals/test_reporting.py` 覆盖 JWT、Bearer、签名 URL、对象 key、Windows 路径、prompt、completion、记忆正文和完整错误消息的禁止提交规则
- [x] 5.6 用确定性 fixture 晋升一份 `stage0-smoke` 示例基线，验证重复 baseline ID 默认不可覆盖

## 6. 接入开发依赖与 CI 质量门禁

- [x] 6.1 新建 `backend/requirements-dev.txt`，固定 pytest、pytest-asyncio、pytest-cov、Ruff 等测试依赖
- [x] 6.2 修改 `backend/pyproject.toml`，移除对整个 `tests/evals` 的默认忽略，并为真实模型/数据库评估增加显式 pytest markers
- [x] 6.3 修改 `.github/workflows/integration.yml`，新增 `backend-unit`、`eval-harness`、`eval-regression-smoke` 和 `frontend-build` jobs，保留 `compose-smoke`
- [x] 6.4 确保普通 push 的强制 jobs 不读取模型 API Key，真实模型评估保留为后续独立 `workflow_dispatch`
- [x] 6.5 配置 CI 上传测试摘要和 smoke 报告 artifact，但不上传含 prompt、completion 或用户内容的原始结果

## 7. 文档校正与阶段 0 验收

- [x] 7.1 更新 `backend/tests/evals/README.md` 和 `QUICKSTART.md`，将当前用例数校正为 24，并记录严格校验、运行模式、报告 Schema 和分类命令
- [x] 7.2 更新 `docs/resume-quantification-plan.md`，把“新增 CI”改为“扩展现有 CI”，并将“先跑全量 eval”调整为“先通过阶段 0 门禁”
- [x] 7.3 运行 `python -m tests.evals.cli validate-suite --expected-count 24`，确认 24/24 用例均被识别且无静默跳过
- [x] 7.4 运行 Ruff、默认 pytest、评估框架测试和回归 smoke fixtures，记录 passed/failed/skipped 与执行时间
- [x] 7.5 在 `frontend` 运行 `npm run build`，在根目录运行 `docker compose config -q`，确认现有构建链路未回退
- [x] 7.6 检查新生成的 `stage0-smoke` 证据不含敏感字段，并记录阶段 1 可以开始的前置条件

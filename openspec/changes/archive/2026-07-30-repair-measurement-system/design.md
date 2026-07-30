## Context

SmartClass 的评估链路分散在 `backend/app/core/evaluation.py`、`backend/tests/evals/evaluators/`、`backend/tests/evals/runners/`、CLI、回归脚本和 GitHub Actions 中。当前 24 个 YAML 用例包含 9 类断言，但模型只声明其中一部分，基础分发器只实现 4 类；Memory/Extraction evaluator 的 `actual_output` 字段与 YAML 断言字段也不一致。分类加载依赖目录名，而实际目录名和 `category` 值不同，导致按类别运行不可靠。

现有报告还混合了平均分与通过率，缺失类别会被回归脚本跳过，原始 JSON 又被 `results/.gitignore` 忽略。最新上下文压缩报告使用 Fake Model，真实模型报告与确定性报告没有机器可读的模式标识。现有 CI 仅验证 Compose 和构建后端镜像。

阶段 0 的目标是让后续所有简历数字具备三项性质：统计口径明确、运行失败不可被隐藏、结果可以从提交的脱敏证据复现。

## Goals / Non-Goals

**Goals:**

- 让当前全部 YAML 用例都能被严格加载、校验和按元数据分类。
- 建立一个断言注册表，保证“Schema 声明、实现、测试、YAML 使用”四者一致。
- 明确 `pass_rate`、`avg_score`、`error_rate` 及分类指标的计算规则。
- 在报告中记录运行模式、模型配置摘要、数据集指纹、代码版本和环境摘要。
- 分离原始结果与可提交的脱敏 benchmark 证据。
- 把确定性质量检查接入现有 GitHub Actions。

**Non-Goals:**

- 本阶段不扩充 Memory、RAG、产物或安全评估数据集。
- 不运行真实模型全量实验，不生成最终简历数字。
- 不修改 LangGraph、记忆、上下文压缩、产物生成等业务行为。
- 不新增线上 API、数据库表或第三方评估平台。

## Decisions

### 1. 用 YAML `category` 作为唯一分类依据

`EvalRunner.load_cases()` 始终递归发现 `cases/**/*.yaml`，完成 Schema 校验后再根据 `EvalCase.category` 过滤。目录仅用于人工组织，不参与运行语义。

同时新增 suite 级静态校验：无法解析、重复 `case_id`、未知类别、未知断言、空断言列表均使校验失败。当前仓库必须能严格识别全部 24 个用例，而不是打印 warning 后继续。

选择这一方案而不是重命名全部目录，是为了降低迁移噪音，并允许同一目录未来容纳多个细分类别。

### 2. 建立显式断言注册表和统一结果结构

在 `BaseEvaluator` 中使用 `AssertionType -> handler` 的显式映射，未注册类型抛出 `UnsupportedAssertionError`。当前 YAML 中的 `count_check`、`encoding_check`、`semantic_match` 要么加入受支持枚举和实现，要么迁移为已有的等价断言；不得仅扩充 Enum 而没有执行逻辑。

Memory 和 Extraction evaluator 输出稳定的、文档化的 `actual_output` 字段。YAML 同步迁移到这些字段，禁止 evaluator 为适配单个旧用例拼装不存在的结果。

确定性断言与 LLM Judge 分离：

- `contains`、`not_contains`、`route_match`、`count_check`、`encoding_check`、结构完整性等属于确定性断言。
- `response_quality` 或 `semantic_match` 属于 Judge 断言，报告必须标记 judge 模型；Judge 异常计为 `ERROR`，不能回退到固定 0.5 分。

### 3. 报告同时保存分数与通过率，但不混用

扩展 `EvalReport`，至少包含：

- `schema_version`
- `run_mode`: `deterministic`、`model-eval` 或 `smoke`
- `total_cases`、`passed`、`failed`、`error`
- `pass_rate`、`error_rate`、`avg_score`
- `category_metrics[category]`: count、passed、failed、error、pass_rate、avg_score
- `dataset_fingerprint`
- `git_commit`
- `model`: provider/model/temperature 的非敏感摘要，可为空
- `environment`: Python、OS 与关键开关摘要

回归阈值对 `pass_rate` 和 `error` 分别判断。任何必需类别缺失或存在 `ERROR` 时，门禁失败。旧报告仍可读取，但必须标记为 legacy，不能自动晋升为新基线。

### 4. 原始运行结果与公开证据分离

保留 `backend/tests/evals/results/*.json` 的忽略规则，作为本地原始结果目录；新增：

- `backend/tests/evals/reporting.py`：从运行结果生成脱敏汇总。
- `backend/tests/evals/manifest.py`：收集 commit、环境、数据集指纹和模型摘要。
- `docs/benchmarks/README.md`：统一实验与报告规范。
- `docs/benchmarks/baselines/<baseline-id>/manifest.yaml`
- `docs/benchmarks/baselines/<baseline-id>/summary.json`
- `docs/benchmarks/baselines/<baseline-id>/report.md`

可提交的 `summary.json` 不包含 prompt、completion、记忆正文、附件正文、JWT、对象 key、宿主路径或完整错误消息。基线由显式 `promote-baseline` 命令生成，普通 `run` 不自动覆盖。

### 5. CI 只运行确定性门禁，真实模型评估独立触发

扩展 `.github/workflows/integration.yml`，增加以下 jobs：

1. `backend-unit`：安装 `requirements.txt` 和新增 `requirements-dev.txt`，运行 Ruff 与默认 pytest。
2. `eval-harness`：运行评估框架自身测试及 `validate-suite --expected-count 24`。
3. `eval-regression-smoke`：使用固定 fixture/fake runtime 生成报告，并验证回归脚本能正确阻断缺失类别、ERROR 和阈值下降。
4. `frontend-build`：`npm ci` 与 `npm run build`。
5. 保留现有 `compose-smoke`。

真实模型、数据库集成和高成本评估不放进每次 push；后续通过 `workflow_dispatch` 或独立 workflow 执行。这样可以避免 CI 因外部模型波动而不稳定，也避免向普通 PR 暴露模型密钥。

### 6. 默认 pytest 纳入评估框架测试

移除 `backend/pyproject.toml` 中对整个 `tests/evals` 的全局忽略。需要真实服务的测试使用 pytest marker 显式标记，默认测试只收集 evaluator/runner/reporting 的确定性单元测试。

这比在 CI 中覆盖 `addopts` 更透明，也避免开发者本地运行 `pytest` 时误以为评估框架已被测试。

## Risks / Trade-offs

- [严格校验会立即暴露现有坏用例，短期内全量评估可能无法运行] → 先提供校验报告，再逐类迁移 YAML 和 evaluator；完成前不生成新基线。
- [报告 Schema 变化影响旧 JSON] → 提供 legacy loader，只读兼容旧字段，新门禁只接受新 Schema。
- [LLM Judge 使结果具有随机性] → 在报告中记录模型参数和重复次数；阶段 0 CI 不运行 Judge。
- [提交 benchmark 汇总仍可能泄露信息] → 使用字段 allowlist 生成摘要，并为脱敏器增加敏感值测试。
- [根仓库使用 backend/frontend 子模块，CI 修改跨多个仓库] → 实施时先在 backend 子模块提交评估改动，再在根仓库提交 workflow、docs 和子模块指针。
- [当前 24 个用例的业务期望本身可能不合理] → 阶段 0 只修执行与口径；业务期望调整必须在报告中单独记录数据集版本变化。

## Migration Plan

1. 为现有 24 个 YAML 生成只读审计清单，列出 category、断言类型和字段引用。
2. 增加严格 Schema、断言注册表和 suite 校验测试，使问题以测试失败形式显现。
3. 迁移 Memory/Extraction YAML 与 evaluator 输出契约，直至 24/24 可加载。
4. 升级报告 Schema 和回归检查，并用 fixtures 验证统计口径。
5. 新增脱敏汇总和 baseline promotion；保留旧 JSON 但标记 legacy。
6. 更新文档和 CI，先在分支验证，再合并。

回滚时可恢复旧 CLI/runner；所有新字段均为报告层变化，不影响线上服务。已生成的新 Schema 报告保留，不降级覆盖旧报告。

## Open Questions

- 第一份可晋升基线的必需类别集合建议为 `intent_recognition`、`memory_retrieval`、`memory_write`、`extraction_quality`、`context_compression`；在阶段 0 实施时根据修复后的 suite 校验结果最终确认。
- `semantic_match` 建议统一迁移为 `response_quality` Judge 断言，避免维护两个语义相近的类型；若现有用例可以用确定性关键词覆盖，则优先移除 Judge 依赖。

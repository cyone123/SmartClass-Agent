## Why

SmartClass 已具备评估用例、运行器、回归检查、观测事件和 CI 雏形，但当前存在断言已声明未执行、分类筛选与目录不一致、报告指标语义混用、缺失类别被静默跳过、结果被 Git 忽略等问题。若直接开展简历量化实验，可能产生不可复现或无法提交验证的数字，因此必须先建立可信的测量基线和证据链。

## What Changes

- 修复评估用例发现与分类筛选，使分类名与 YAML 中的 `category` 成为唯一口径。
- 为当前用例实际使用的断言提供完整实现或在校验阶段明确拒绝，禁止运行时静默返回未知断言。
- 统一 `passed`、`failed`、`error`、平均分、分类通过率和分类平均分的定义，并让报告记录模型、环境、代码版本与数据集版本。
- 强化回归门禁：缺失必需类别、存在运行错误、低于类别阈值时均以非零状态失败。
- 建立可提交的脱敏 benchmark 汇总与实验清单，同时继续忽略可能含用户内容的原始运行结果。
- 扩展现有 GitHub Actions，分别执行后端单测、评估框架测试、评估用例静态校验、回归冒烟和前端构建。
- 更新评估文档中的用例数量、命令、指标口径和报告留存规则。

## Capabilities

### New Capabilities

- `evaluation-harness-integrity`: 评估用例发现、断言执行、错误处理、统计语义和回归判定必须一致且可测试。
- `benchmark-evidence-management`: 量化实验必须生成带环境与版本信息的脱敏、可提交证据，并将原始敏感结果与公开汇总分离。
- `ci-quality-gates`: CI 必须运行确定性测试、评估静态校验、回归冒烟与前端构建，并在缺失或失败时阻断。

### Modified Capabilities

<!-- No existing capability requirements are changed by this proposal. -->

## Impact

- 后端评估核心与运行器：`backend/app/core/evaluation.py`、`backend/tests/evals/`
- 回归与报告工具：`backend/tests/evals/check_regression.py`、新增报告汇总/清单模块
- 测试配置：`backend/pyproject.toml`、`backend/tests/evals/**/test_*.py`
- CI：`.github/workflows/integration.yml`
- 证据与文档：`docs/benchmarks/`、`backend/tests/evals/README.md`、`docs/resume-quantification-plan.md`
- 不改变线上 API、数据库模型、Agent 主流程、Prompt 或用户数据格式。

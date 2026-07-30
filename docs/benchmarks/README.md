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

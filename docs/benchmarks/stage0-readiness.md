# 阶段 0：测量系统修复验收

日期：2026-07-30

## 结论

阶段 0 的离线测量基础设施已达到“可以开始阶段 1 真实模型实验”的代码与本地验收条件。当前 `stage0-smoke` 是确定性 fixture 证据，只证明评估契约、统计、回归门禁和脱敏晋升链路可运行，不能作为模型质量、时延或简历业务指标。

## 本地验收结果

| 门禁 | 结果 | 样本/耗时 |
| --- | --- | --- |
| 严格 YAML 校验 | PASS | 24/24；6 个分类 |
| Ruff | PASS | `app` + `tests`，0 error |
| 默认后端 pytest | PASS | 165 passed，0 failed，9.80s |
| 评估 harness pytest | PASS | 43 passed，0 failed，4.33s |
| 通过型回归 fixture | PASS | 6/6 category，error=0 |
| 失败型回归 fixtures | PASS | 阈值下降、缺失分类、运行错误、legacy 均被拒绝 |
| 前端生产构建 | PASS | 3471 modules，10.45s |
| Docker Compose 配置 | PASS | `docker compose config -q` |
| smoke 证据敏感模式扫描 | PASS | 未发现 prompt、completion、JWT、签名 URL、对象 key、Windows 路径或记忆正文模式 |

前端构建仍报告既有的 OnlyOffice 非 module script 提示和大于 500 kB chunk 警告，不影响本阶段通过；它们应作为后续前端性能优化项，而不是评估结果。

## 已建立的保护

- 24 个 YAML 递归发现，坏 YAML、重复 ID、未知断言和非法字段均 fail-closed。
- 断言使用显式注册表；Judge 不可用时记为错误，不再返回固定中间分。
- Memory、Extraction、Intent 和 Context Compression 使用稳定输出字段。
- Schema 2.0 分开记录通过率、错误率、平均分和分类指标。
- 回归阈值从版本化 YAML 读取；缺少必需分类、任何运行错误、阈值下降或 legacy 报告均失败。
- 原始 JSON 继续被忽略；只有通过门禁的 allowlist 聚合数据可以晋升到 `docs/benchmarks/`。
- 现有 CI 已扩展后端、评估、回归 smoke、前端和 Compose jobs；普通 push 不读取真实模型 Key。

## 阶段 1 开始条件

1. 合并前确认 GitHub Actions 的 5 个 jobs 在目标分支全部通过。
2. 固定模型供应商、模型名、温度、重试、数据库快照和 24 用例数据集 fingerprint。
3. 使用独立人工触发环境运行 `model-eval`，禁止把真实 Key 放入普通 push job。
4. 对同一配置至少重复运行并记录样本量、失败归因、运行成本和置信限制，不能用一次结果代表稳定性能。
5. 只有 Schema 2.0 且通过回归门禁的报告才能晋升；简历只引用晋升报告里的真实模型或压测数字。

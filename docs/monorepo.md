# Monorepo 开发与 CI

`backend/`、`frontend/`、`landing-page/` 是主仓库直接跟踪的普通目录，统一在根仓库查看状态、创建分支和提交。迁移以原主仓库 HEAD 为父提交追加一个提交，不重写主仓库历史；三个原子仓库导入迁移时的文件快照，不将它们的独立提交历史合并进主仓库。

## 获取与开发

```bash
git clone https://github.com/cyone123/SmartClass-Agent.git
cd SmartClass-Agent
```

曾使用子模块的旧工作副本，建议另行克隆迁移后的仓库，并将自己的本地环境文件复制到原有位置；旧工作副本可留作历史查询。不要在新仓库运行 `git submodule update`。

各应用保留自己的依赖清单、锁文件和构建命令，不引入根级 npm workspace。后端命令仍在 `backend/` 执行，两个 Web 应用分别在自己的目录执行 `npm ci` / `npm run build`。

## 环境变量

环境变量不合并、不移动：后端继续读取根目录 `.env`，Compose 继续使用根目录 `.env.docker`，各 Web 应用保持原有环境文件约定。现有 `.env.local.example`、`.env.docker.example` 保留。真实环境文件及其本地变体由 Git 忽略。

## GitHub Actions

工作流统一位于根目录 `.github/workflows/`，checkout 不再拉取子模块。

| 工作流 | 检查 |
| --- | --- |
| `integration.yml`（CI） | 后端 Ruff 检查及格式检查、Linux/Windows 默认测试及 coverage、24 个评估用例离线校验、评估基础设施测试、fail-closed 回归 fixture 和脱敏 baseline smoke、Vue 前端构建、Next.js 落地页构建、Compose 配置及后端镜像构建 |
| `eval.yml`（Agent Evaluation） | PostgreSQL/pgvector 服务、真实模型评估、回归门禁及评估报告上传 |

CI 在 main push、pull request 和手动运行时触发。真实模型评估保留 main pull request 与手动触发；需要在 **SmartClass-Agent 主仓库** 的 Actions secrets 中配置 `EVAL_MODEL`、`EVAL_API_KEY`、`EVAL_BASE_URL`。GitHub 不会自动从原后端仓库迁移 secrets。缺少配置时真实模型评估显示跳过提示，离线门禁仍执行；配置后模型评估失败或回归门禁失败会使工作流失败。

主仓库如启用了分支保护，请将 required checks 更新为根工作流实际生成的检查名称，尤其是 `backend-unit (ubuntu-latest)`、`backend-unit (windows-latest)` 和新增的 `landing-page-build`。

## 本地迁移备份

执行迁移的工作副本保留 `.git/modules/` 中的原 Git 数据，以及 `.git/monorepo-backup/` 中三个子仓库的 Git bundle 和迁移前版本清单。这些仅用于本地恢复和历史查询，不提交或上传。其他克隆不包含此备份；原主仓库旧提交中的子模块指针保持原样。

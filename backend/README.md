# SmartClass Agent Backend

<div align="center">

**🎓 SmartClass 教学智能体后端**（FastAPI · LangGraph · PGVector · MinIO）

[![CI](https://github.com/cyone123/SmartClass-Agent/actions/workflows/integration.yml/badge.svg)](https://github.com/cyone123/SmartClass-Agent/actions/workflows/integration.yml)
[![Agent Evaluation](https://github.com/cyone123/SmartClass-Agent/actions/workflows/eval.yml/badge.svg)](https://github.com/cyone123/SmartClass-Agent/actions/workflows/eval.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)](https://github.com/langchain-ai/langgraph)

</div>

---

## 概述

SmartClass Agent 后端，提供对话式教学智能体的核心服务：LangGraph Agent 工作流、RAG 检索、长期记忆、产物生成（PPT / DOCX / HTML 互动）、对象存储抽象与 JWT 认证。详见 monorepo [SmartClass-Agent](https://github.com/cyone123/SmartClass-Agent)。

主图由一个动作式对话入口处理普通回复、教学设计和产物修改，再由一个教学 intake Agent 基于当前任务消息追问；只有完整需求才物化 `teaching_metadata` 并进入持久审批。旧主图拓扑与切换开关已移除。完整契约见 monorepo 的 `docs/main-graph-orchestration.md`。

## CI 门禁

| Workflow | 触发 | 作用 |
| --- | --- | --- |
| [`ci.yml`](.github/workflows/ci.yml) | push / PR | ruff lint + format check、pytest（Ubuntu + Windows 双平台矩阵）、覆盖率 |
| [`eval.yml`](.github/workflows/eval.yml) | PR / 每日定时 / 手动 | pgvector 服务容器 + Agent 评估套件 + `check_regression` 阈值回归门禁 |

L1 确定快速免费（每次提交）；L2 非确定慢花钱（低频 + 定时巡检），用阈值而非快照对抗模型非确定性。

## 本地开发

```bash
pip install -r requirements.txt
python -m ruff check app tests        # lint
python -m ruff format --check app tests  # format check
python -m pytest tests -q             # 单测（默认排除 tests/evals）
python -m tests.evals.cli list-categories  # 评估用例
```

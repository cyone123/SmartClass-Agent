# 真实模型评估首次尝试记录

日期：2026-07-30

## 目标与范围

- 目标：在 24 用例全量运行前，用 `intent_basic_chat_001` 做单用例真实模型 smoke。
- 数据：仓库内合成评估输入，不包含真实用户附件或聊天记录。
- 外部提供方：阿里云 DashScope。
- 本地依赖：Docker Compose PostgreSQL，供 LangGraph checkpointer 与 memory store 使用。

## 结果

真实模型 smoke **未形成可用质量结果**，不得写入简历或晋升为 baseline。

执行过程中识别出三类前置问题：

1. 根目录 `.env` 的 `DB_HOST=postgres` 只适用于 Compose 网络，宿主机 Python 无法解析。
2. 使用 `localhost` 时连接池优先尝试 IPv6，导致初始化超时；限定为 `127.0.0.1` 后数据库链路恢复。
3. 数据库与外部网络链路恢复后，模型端点返回 `403 AllocationQuota.FreeTierOnly`，表示免费额度耗尽。

最终 smoke：1 case，0 passed，0 failed，1 error。该结果是供应商配额错误，不是模型质量失败，也不提供可信时延数据。

## 已完成修复

- CLI 新增 `--local-docker-db`，安全读取 `.env.docker` 并通过 `127.0.0.1` 连接本地容器。
- 运行时错误保存报告后返回非零退出码。
- manifest 自动记录 provider、主模型及 structured/fast/small/memory 模型角色，不记录 API Key 或完整端点。
- 完整 suite 同时含模型和确定性用例时标记为 `mixed`；每个分类单独记录 `run_mode`。
- 新增单元测试覆盖数据库映射、模型摘要脱敏和 mixed 模式统计。

## 恢复条件

1. 在 DashScope 控制台补充可用额度，或由项目所有者明确指定另一个已授权模型配置。
2. 重新运行：

   ```bash
   python -m tests.evals.cli run \
     --case-id intent_basic_chat_001 \
     --local-docker-db \
     --verbose
   ```

3. 单用例无 `ERROR` 后再运行完整 suite。
4. 只有通过回归门禁的 Schema 2.0 聚合报告才能晋升；原始 JSON 继续留在被 Git 忽略的 `backend/tests/evals/results/`。

## 恢复结果

额度恢复后，单用例 smoke 通过。经过评估驱动修复和全量复测，最终基线达到 23/24（95.83%）、0 ERROR，并已晋升为 `stage1-model-eval-2026-07-30`。完整方法与结果见 `docs/benchmarks/stage1-model-eval-2026-07-30.md`。

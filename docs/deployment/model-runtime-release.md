# 模型运行时发布与回滚

## 发布前

1. 备份当前 YAML、环境变量名称清单和部署版本；不要复制密钥到报告。
2. 先应用可空的 `agent_runs.model_config_snapshot` 迁移。旧行保持可读，首次继续执行前由新程序一次性
   接纳当前合法配置并持久化 `legacy_snapshot_adopted`，模型调用必须发生在持久化之后。
3. 离线执行 pytest、Ruff、24 用例清单校验和 OpenSpec strict 校验。
4. 分别执行显式 live smoke；缺凭据或权限的 provider 保持 `unverified`。不得用 OpenRouter 路由结果
   替代 DeepSeek/智谱直连结果，也不得把默认 pytest 当作 live 证明。
5. 先保留完整 legacy env，以现有 `openai_chat` 流程灰度；随后按角色启用 YAML 连接并重启。

## 快照兼容演练

- 新 run 在第一次模型调用前已持久化不可变配置封套。
- 教学要素确认、教学计划确认、并行三类产物及后台反思沿用工作流/入队时快照。
- 新修改任务或明确重启选择接纳时固定的新配置，不修改旧快照。
- 旧记录无快照时只接纳一次；接纳或持久化失败时零模型请求。
- 删除固定快照引用的凭据会得到明确认证/配置失败，不会切换账号。

对应确定性演练由 `tests/test_model_workflows.py`、`tests/test_model_access.py` 与
`tests/test_stage5_business_regression.py` 执行；结果记录在 OpenSpec 变更的阶段 5 验证文档中。

## 回滚

仅回退 YAML 时，保留当前程序和可空数据库列，恢复原配置/凭据并重启；已固定任务仍按自身快照恢复。

若要回滚到不理解多协议历史的旧程序：

1. 停止接收新任务和 memory reflection worker。
2. 完成或显式取消所有使用 Anthropic/Gemini/新 provider 历史的活动及待审批工作流。
3. 确认没有此类后台反思任务后再部署旧程序；旧程序不得直接恢复这些 checkpoint。
4. 不执行破坏性降表，保留可空快照列，便于重新升级和审计。
5. 恢复旧版完整角色身份。不能通过删除 key 迫使系统隐式选用其他账号；缺 key 应保持明确失败。

回滚后重新运行旧路径业务 smoke，核对审批仍存在、SSE 事件类型未变化、workspace 与 StorageService
边界未被绕过。

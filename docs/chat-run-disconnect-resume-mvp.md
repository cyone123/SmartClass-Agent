# Agent 对话断网续跑 MVP

## 能力边界

第一阶段将一次对话拆成持久化 Run、后台执行任务和可重放 SSE 订阅。浏览器切换会话、离开 ChatPanel 或网络暂时断开时，只会终止当前事件订阅；FastAPI 进程中的 Agent Run 会继续执行，并把事件写入 PostgreSQL。

本阶段保证：

- 同一 FastAPI 进程存活期间，客户端断连不会取消 Agent、LangGraph、上下文压缩或产物分支。
- 客户端可按事件序号补放 `metadata`、`progress`、`token`、`artifact`、`artifact_trace`、`approval`、`suggestions`、`error` 和 `done`。
- 切回会话或页面重新挂载时，前端会发现该 thread 的 active run，恢复输出快照，并从游标继续订阅。
- 只有显式调用取消接口才会请求取消 Run。
- LangGraph `interrupt()` 审批仍保持原语义；到达审批的 Run 结束为 `waiting_approval`，用户确认后创建新的恢复 Run。

本阶段不保证：

- 后端进程、容器或宿主机退出后继续执行正在进行的模型/产物任务。
- 多 Uvicorn worker 或多副本之间共享运行任务。
- Worker 崩溃后的自动领取、重试、死信或 exactly-once。
- 产物生成在进程崩溃场景下完全幂等。

应用启动时会把遗留的 `queued/running` MVP Run 标为 `failed` 并补充终态事件，避免它们永久显示为进行中。独立 Worker、lease/heartbeat、崩溃恢复和 artifact execution key 属于第二阶段。

## API

### 创建 Run

`POST /api/chat/runs`

请求体沿用原 `ChatRequest`，但持久化 Run 必须提供 `thread_id`。成功返回 `202` 和 Run 快照。若同一 thread 已有 `queued/running` Run，返回 `409` 及现有 Run 快照。

### 查询与发现

- `GET /api/chat/runs/{run_id}`：查询当前用户拥有的 Run。
- `GET /api/chat/runs/active?thread_id=...`：查询该会话当前 `queued/running` Run。
- `POST /api/chat/runs/{run_id}/cancel`：显式取消 active Run。

### 补放与跟随事件

`GET /api/chat/runs/{run_id}/events?after_sequence=N`

响应为 SSE。每个持久化事件带有：

```text
id: 42
event: token
data: {"run_id":"...","text":"..."}
```

客户端也可以发送 `Last-Event-ID`。服务端先按升序补放大于游标的事件，再等待新事件；15 秒无业务事件时发送 SSE heartbeat。`done` 事件包含 `run_id` 和最终 `status`。

所有 Run API 都按当前登录用户和 thread 归属鉴权。状态响应不包含持久化的原始 message、attachment id 列表或 approval 请求体；这些执行输入也不会进入 observability fields。

## 数据与部署

`agent_runs` 保存生命周期、执行输入、输出文本快照、最后事件序号和时间戳；`agent_run_events` 以 `(run_id, sequence)` 保证 Run 内有序。当前使用 PostgreSQL 轮询跟随事件，不新增 Redis 等基础设施。

Nginx 对 `/api/chat/runs/{run_id}/events` 关闭 buffering/cache，并沿用一小时读写超时。旧 `/api/chat/stream` 暂时保留，便于旧客户端和回滚。

当前实现要求单 FastAPI worker。启用多 worker 或水平扩容前，必须先完成第二阶段的独立任务领取和租约方案。

## 验证

后端：

```powershell
cd backend
python -m pytest -q
python -m ruff check app tests
python -m ruff format --check app tests
```

前端：

```powershell
cd frontend
npm run test:chat-run
npm run build
```

建议手工验证：发送一个耗时请求后切换到其他会话，等待数秒再切回；确认原 Run 仍为 `running`、输出从快照继续追加，并且没有重复 token。再使用浏览器离线模式短暂断网，恢复网络后确认 SSE 从最后序号续接。

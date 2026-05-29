## Why

当前 agent workspace 代码执行仍依赖后端宿主机本地 `subprocess`，虽然已有路径、防安装命令、超时和输出截断等护栏，但执行环境仍与应用进程共享机器边界。随着产物生成、文件分析和后续更复杂的 agent 代码执行增加，需要把运行时隔离到可治理、可回收、可观测的沙箱环境中。

Daytona sandbox 可以作为远程隔离执行环境承载 agent 工作区代码，帮助 SmartClass 降低宿主机风险，并为后续资源配额、网络策略、生命周期管理和执行审计提供统一基础。

## What Changes

- 引入 Daytona 作为 agent workspace 代码执行的可选后端，保留现有本地执行后端作为兼容或开发 fallback。
- 在后端配置层新增 Daytona API、默认 snapshot/image、生命周期、网络策略和执行超时等配置项。
- 在 `backend/app/core/workspace.py` 现有 `ExecutionBackend` 抽象下新增 Daytona 执行实现，维持 `WorkspaceToolset` 对 agent 暴露的工具契约不变。
- 将 workspace 文件写入、代码执行、输出文件收集映射到 Daytona sandbox 文件系统与 process/code execution API。
- 为 sandbox 创建、复用、停止/删除、失败归因和输出收集补充结构化错误、日志字段和测试覆盖。
- 默认保持安全收敛：禁止依赖安装命令、限制执行超时、截断输出、按配置控制网络访问，最终产物仍必须进入现有 artifact 链路。

## Capabilities

### New Capabilities

- `agent-sandbox-execution`: agent workspace 代码可以通过 Daytona sandbox 后端执行，并保持现有 workspace 工具、安全策略、输出收集和 artifact 链路契约。

### Modified Capabilities

无。当前 `openspec/specs/` 下没有既有 capability；本次以新增 capability 描述 Daytona 沙箱执行能力。

## Impact

- 后端核心模块：`backend/app/core/workspace.py`、配置层、必要的错误类型与日志调用点。
- Agent 产物链路：PPT、DOCX、HTML 互动内容等依赖 `run_workspace_code` 的子 agent 执行路径。
- 配置与部署：需要安装 Daytona Python SDK，并通过环境变量或配置文件提供 Daytona 凭据、API URL、target、snapshot/image、生命周期和网络策略。
- 测试：新增 workspace 执行后端单元测试、配置测试、失败分类测试，以及本地 fallback 行为测试。
- 运维与安全：新增 sandbox 生命周期清理、执行审计字段、网络默认策略、敏感信息不落日志约束。

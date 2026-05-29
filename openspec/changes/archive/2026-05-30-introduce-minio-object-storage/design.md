## Context

SmartClass 当前有三条文件链路：knowledge files 面向 RAG，attachment files 面向会话上下文分析，artifact files 面向 Agent 生成与修改后的用户可见产物。本次需求聚焦会话附件和 Agent 产物，同时必须覆盖产物下载、HTML 在线预览、OnlyOffice 文档预览与回写。

现有实现把 `storage_path` 当成本地绝对路径使用：附件上传在 `file_service.py` 里写入 `backend/storage/attachments/...`，artifact ready 时在 `artifact_service.py` 里 `shutil.copy2` 到 `backend/storage/artifacts/...`，下载和预览 API 在 `api/file.py` 中通过 `Path(storage_path)`、`FileResponse`、`read_text` 读取内容。这个实现简单，但把业务逻辑、预览逻辑和存储介质绑死在本地磁盘上。

## Goals / Non-Goals

**Goals:**

- 引入统一存储抽象，支持本地存储和 MinIO/S3 兼容对象存储。
- 让新上传的会话附件和新生成的 artifact 通过配置选择本地或 MinIO 存储。
- 保持前端 API、SSE artifact payload、artifact revision 关系和 HTML iframe sandbox 预览语义稳定。
- 让需要本地路径的附件分析、语音转写、视频分析、OnlyOffice 回写等组件通过受控临时文件访问对象内容。
- 对存储操作补充可观测字段、失败分类和用户可读错误摘要。

**Non-Goals:**

- 不在本次强制迁移历史本地文件到 MinIO。
- 不把 knowledge/RAG 文件作为第一阶段迁移目标；但共享接口需要兼容 OnlyOffice 对 knowledge file 的既有回写。
- 不要求前端直接访问 MinIO bucket，也不在前端保存对象 key。
- 不改变 Agent workspace 执行后端、LangGraph 节点、审批中断或 SSE 事件类型。

## Decisions

### Decision 1: 新增存储服务作为业务层唯一入口

新增 `StorageBackend` 和 `StorageService`，提供 `put_bytes`、`put_file`、`open_stream`、`read_text`、`materialize_temp_file`、`delete`、`exists`、`build_download_response` 或等价能力。本地后端继续使用 `Path`，MinIO 后端使用 MinIO/S3 SDK。

Rationale:

- 业务代码不再散落 `Path(storage_path)`，后续接 S3/OSS 或迁移 knowledge files 时有稳定边界。
- API 层可以统一决定代理下载、presigned redirect、HTML 文本读取和 OnlyOffice fetch URL。
- 附件分析等必须拿文件路径的旧组件可以用临时文件适配，不要求一次性改掉所有解析器。

Alternatives considered:

- 直接把 `storage_path` 写成 `minio://bucket/key` 并在各处判断 scheme。实现快，但会继续扩散存储判断。
- 前端直接使用 MinIO presigned URL。下载可行，但 HTML preview、OnlyOffice callback、安全审计和 URL 过期策略会变得分散。

### Decision 2: 数据库采用兼容扩展，保留 `storage_path`

为 `attachment_files` 和 `artifact_files` 增加 `storage_backend`、`storage_key` 字段，`storage_path` 保留用于历史本地文件和兼容 schema。新 MinIO 文件写入 `storage_backend='minio'`、`storage_key='<kind>/...'`，`storage_path` 可保存兼容标识或生成时的 legacy path，但读取时优先使用新字段。

Rationale:

- 可以无损读取现有本地记录，避免一次性迁移历史文件。
- 新代码依赖 storage key，符合后续对象存储契约。
- 数据库仍能兼容当前 schema 中已有的 `storage_path` 非空约束。

Alternatives considered:

- 只复用 `storage_path` 字段保存对象 key。迁移最小，但字段语义混乱，后续调试与校验容易误用。
- 新建独立 `stored_objects` 表。长期更规范，但第一阶段会放大迁移范围；当前只需覆盖 attachment/artifact 两类对象。

### Decision 3: Artifact ready 流程仍由 artifact service 收口

Agent 子流程继续在 workspace 中生成本地输出文件，`artifact_service.mark_artifact_ready` 负责校验输出文件、上传到存储后端、更新 artifact metadata、维护 `is_current` 与 revision 关系。workspace 只负责生成，artifact service 负责收集入库。

Rationale:

- 符合当前统一 artifact 模型，不让 Agent workspace 直接决定用户可见存储位置。
- 上传失败能统一进入 artifact `failed` 状态和 SSE `artifact` 事件。
- revision 关系、MIME 推断、size、title 更新保持集中。

Alternatives considered:

- 让产物子 Agent 直接上传 MinIO。会绕过权限、状态、审计和 revision 维护，不符合当前 Agent 治理方向。

### Decision 4: 下载和预览保留后端路由，内部可代理或签名

现有 `/file/download/{file_kind}/{file_id}`、`/file/preview/artifact/{file_id}`、`/file/content/artifact/{file_id}` 和 `/file/config/{file_kind}/{file_id}` 继续存在。下载默认由后端代理流式返回；如配置允许，可对非敏感下载使用短 TTL presigned redirect。HTML preview 总是由后端读取 HTML 并嵌入现有 sandbox iframe。OnlyOffice document URL 使用可公开访问的后端 URL 或短期签名 URL。

Rationale:

- 前端 artifact 对象不需要理解 MinIO。
- HTML preview 可以继续施加 iframe sandbox 和统一错误处理。
- OnlyOffice 的可访问性由 `PUBLIC_API_BASE_URL` 和 URL 策略集中治理。

Alternatives considered:

- 所有下载都直接 presigned redirect。后端负载更低，但错误处理、审计和 URL 泄漏风险更高。

## Risks / Trade-offs

- MinIO 不可用会影响新附件上传和 artifact ready。Mitigation: 本地存储保持默认；MinIO 初始化失败早发现；上传失败将 artifact/attachment 返回明确错误。
- OnlyOffice 需要能访问 document URL。Mitigation: 保留后端 public URL 代理模式，并让 presigned URL TTL 可配置。
- 一些现有解析器仍要求本地路径。Mitigation: `materialize_temp_file` 统一生成临时文件并清理，逐步改造解析器接受 stream。
- 启动期补丁式迁移会继续存在。Mitigation: 本次仅做 additive nullable columns，并在任务中增加迁移测试；后续再转显式迁移体系。
- 大文件经后端代理可能增加带宽压力。Mitigation: 先保证一致性与安全，后续可按配置对下载启用短 TTL presigned redirect。

## Migration Plan

1. 添加配置、依赖和存储服务，本地后端作为默认实现。
2. 添加 `storage_backend`、`storage_key` 等兼容字段，读取时优先新字段，缺失时回退 legacy `storage_path`。
3. 改造附件上传与读取，保证附件分析、语音、视频链路通过临时文件继续可用。
4. 改造 artifact 创建、ready、failed、下载、HTML preview、OnlyOffice config/callback。
5. 增加测试覆盖本地兼容、MinIO fake/mock、失败路径和预览链路。
6. 部署时先以 local 后端上线验证，再切换测试环境 MinIO，最后按环境变量启用生产 MinIO。

Rollback strategy: 将存储后端配置切回 `local`。已写入 MinIO 的新对象仍由记录中的 `storage_backend/storage_key` 读取；若需要完全回滚，可运行一次离线对象导出脚本把对象复制回本地并更新记录。

## Open Questions

- MinIO bucket 是否由应用启动时自动创建，还是由部署流程预先创建。
- 下载默认是否始终代理，还是允许对大文件启用 presigned redirect。
- 历史本地 artifact/attachment 是否需要后续单独迁移任务。

## Why

SmartClass 目前把会话附件和 Agent 生成产物直接写入后端本地 `storage` 目录，并在上传、产物收集、下载、HTML 预览与 OnlyOffice 回写链路中大量使用 `Path(storage_path)`。随着附件、PPT/DOCX/HTML 产物、产物 revision 和在线预览增多，本地文件存储会限制部署弹性、跨实例访问、备份治理与后续对象存储迁移。

本变更引入 MinIO 兼容对象存储作为附件与产物文件的可配置存储后端，同时保留本地存储兼容路径，让现有主流程能稳定迁移而不破坏 artifact、attachment、SSE 与预览契约。

## What Changes

- 新增统一存储服务抽象，封装本地文件与 MinIO/S3 兼容对象读写、删除、元数据、URL 生成和临时本地文件访问。
- 新增 MinIO 配置项与依赖，支持 endpoint、bucket、access key、secret key、region、secure/path-style、presigned URL TTL、后端代理下载策略等配置。
- 将会话附件上传链路改为通过存储服务保存文件，数据库保留稳定 storage key，并兼容已有 `storage_path` 字段。
- 将 Agent 产物生成与收集链路改为先从 workspace 输出收集到 artifact 服务，再由 artifact 服务写入对象存储，继续维护 revision、ready/failed 状态和 SSE `artifact` 事件。
- 改造产物下载、HTML 在线预览、OnlyOffice 配置与回写链路，使其通过存储服务读取或写回对象，而不是直接依赖本地 `Path`。
- 保留本地存储作为默认后端和回滚路径；知识库文件/RAG 本体迁移不作为本次必选目标，但新存储接口应为后续接入预留能力。

## Capabilities

### New Capabilities

- `object-storage`: 统一附件与产物文件存储抽象，并支持 MinIO 作为对象存储后端，覆盖上传、下载、Agent 产物收集、HTML 预览、OnlyOffice 预览与回写。

### Modified Capabilities

- None. 当前 `openspec/specs/` 中只有 `agent-sandbox-execution`，本变更不修改其既有要求。

## Impact

- 后端配置与依赖：`backend/app/config.py`、后端依赖清单、环境变量示例或开发说明。
- 后端存储服务：新增 `StorageBackend`/`StorageService` 等模块，接入本地和 MinIO 实现。
- 文件链路：`backend/app/services/file_service.py` 的附件上传、附件读取、语音/视频附件临时文件访问。
- 产物链路：`backend/app/services/artifact_service.py` 的 running artifact 创建、ready artifact 收集、revision 保存和序列化 URL。
- 预览与下载 API：`backend/app/api/file.py` 的下载、HTML content/preview、OnlyOffice config、OnlyOffice callback。
- 数据模型与 schema：`AttachmentFile`、`ArtifactFile` 需要稳定 storage key/backend 字段或等价兼容方案，并保持前端 artifact 对象契约不破坏。
- 测试：新增本地后端兼容测试、MinIO mock/fake 后端测试、附件上传、artifact ready、HTML 预览、OnlyOffice 回写与失败分类测试。

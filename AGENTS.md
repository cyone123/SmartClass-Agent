# SmartClass Agent `AGENTS.md`

## 1. 文档定位

本文件是仓库根目录的主规范，面向参与本项目的 AI 开发代理与工程师。

目标不是介绍产品，而是提供一份可直接驱动开发的执行文档，帮助 AI：

- 准确理解项目当前真实状态，而不是把 roadmap 当成已实现能力
- 在前后端、Agent、RAG、文件处理之间保持一致的数据契约
- 优先做高价值、低歧义的改动，减少返工和错误假设

## 2. 项目定位

这是一个面向教师的多模态互动式教学智能体，目标是帮助老师完成备课、教学设计、教案生成、PPT 生成与互动内容生成。

当前项目阶段不是“完整产品”，而是“已实现主流程功能，待增强Agent Harness治理，工程化补齐”的开发阶段。

3. 当前技术栈与事实入口

### 后端

- FastAPI
- LangChain
- LangGraph
- PostgreSQL
- SQLAlchemy
- PGVector 风格 RAG
- OpenAI 兼容模型接口

关键事实入口：

- [`backend/app/core/graph.py`](./backend/app/core/graph.py)
- [`backend/app/core/agent.py`](./backend/app/core/agent.py)
- [`backend/app/services/file_service.py`](./backend/app/services/file_service.py)
- [`backend/app/core/skills.py`](./backend/app/core/skills.py)
- [`backend/app/core/rag.py`](./backend/app/core/rag.py)
- [`backend/app/core/workspace.py`](./backend/app/core/workspace.py)
- [`backend/app/core/progress.py`](./backend/app/core/progress.py)

### 前端

- Vue 3
- Vite
- Element Plus
- Pinia
- OnlyOffice 文档预览

关键事实入口：

- [`frontend/src/components/ChatPanel/index.vue`](./frontend/src/components/ChatPanel/index.vue)
- [`frontend/src/components/ContextPanel/index.vue`](./frontend/src/components/ContextPanel/index.vue)
- [`frontend/src/components/FilePreviewPanel/index.vue`](./frontend/src/components/FilePreviewPanel/index.vue)
- [`frontend/src/api/file.js`](./frontend/src/api/file.js)
- [`frontend/vite.config.js`](./frontend/vite.config.js)

## 4. 仓库结构速览

```text
demo/
├─ backend/
│  ├─ app/
│  │  ├─ api/          # chat / file / plan / session 接口
│  │  ├─ core/         # graph、agent、rag、skills、llm、progress
│  │  ├─ models/       # SQLAlchemy 模型
│  │  ├─ schemas/      # API schema
│  │  └─ services/     # 业务逻辑
│  ├─ skills/          # docx / pdf / ppt-generator skills
│  ├─ storage/         # 上传文件与附件存储
│  └─ tests/
└─ frontend/
   ├─ src/
   │  ├─ api/
   │  ├─ components/
   │  ├─ layout/
   │  ├─ router/
   │  └─ store/
   └─ AGENTS.md
```

## 5. 当前能力矩阵

### 已实现

- 教学计划、会话、知识库文件、附件的基础 CRUD 接口已经存在
- LangGraph 主流程已经具备基础骨架：
  - 意图识别
  - 教学要素抽取
  - 追问补全
  - 中断并等待用户补充输入
  - RAG 向量检索
  - 教学设计规划
- 附件分析入口已经存在，附件会通过 agent + skills 做文档分析
- Skill registry 已实现，当前已有 `pdf`、`docx`、`ppt-generator` 三类 skills
- 知识库文件异步入库链路已实现
- 前端聊天已接入 SSE 流式响应
- 后端驱动的流程进度卡片
- 前端ai消息 Markdown 实时渲染
- 前端已有附件上传能力
- 前端已接入 OnlyOffice 预览知识库文件
- 语音输入和视频附件分析
- Agent产物生成闭环、选择性生成产物
- 产物生成流程前端可视化
- 产物的差量修改

## 6. 当前真实数据流

### 6.1 对话主链路

1. 前端通过 `/api/chat/stream` 发起请求。
2. 后端根据 `thread_id` 找到会话与 `plan_id`。
3. 如果存在附件，先通过附件分析链路生成 `attachment_text`。
4. LangGraph 根据当前状态进入：
   - 普通聊天
   - 教学规划主流程
5. 教学规划主流程当前实际包含：
   - 意图路由
   - 教学元数据抽取
   - 信息不完整时追问并中断
   - 信息完整时 RAG 检索
   - 教学设计规划输出
6. SSE 当前实际发送的事件主要是：
   - `metadata`
   - `message`
   - `done`

### 6.2 知识库文件链路

1. 上传到 `knowledge_files`
2. 后端异步入队
3. `FileIngestionRuntime` 消费队列
5. 前端轮询知识库文件状态并展示“待解析 / 特征解析中 / 已解析 / 失败”

### 6.3 会话附件链路

1. 上传到 `attachments`
2. 文件按 `plan_id + thread_id` 归属存储
3. 发送消息时携带 `attachment_ids`
4. 后端先做附件分析，再把摘要注入图输入

## 7. 关键现实约束

### 7.1 模型与 skill 约束

- 当前后端实际模型封装在 [`backend/app/core/llm.py`](./backend/app/core/llm.py)，使用的是 `ChatOpenAI`
- skill 风格参考 Anthropic 的 progressive disclosure 思路，但运行时不是 Anthropic SDK
- AI 不要把“Anthropic 风格 skill 文档”误判为“Anthropic 模型运行时”

### 7.2 文件链路约束

- `knowledge_files` 与 `attachments` 是两条不同链路
- `knowledge_files` 面向知识库和 RAG
- `attachments` 面向单次或多轮会话中的上下文分析
- 任何新增多模态能力都必须先明确属于哪条链路，不能混用

### 7.3 平台与工具约束

- 当前项目运行环境对 Windows 友好
- Shell、路径、OnlyOffice 接入都应保持 Windows 兼容
- 不要默认依赖 Linux-only 的处理方式
- 涉及 Office、PDF、PPT 的处理优先复用现有 skill/script，而不是直接让模型裸处理二进制内容

### 7.4 Git 与工作区约束

- 提交前先确认当前 git 根目录与工作区状态
- 不要假设这是一个绝对干净、单一边界的 monorepo
- 前后端目录的提交边界、权限状态、safe.directory 状态都可能需要先确认

### 7.5 编码与文本约束

- 文本、提示词、文档默认使用 UTF-8
- 如果出现中文乱码，优先处理编码问题，不要在乱码文本上继续堆功能

## 8. AI 开发原则

- 先补数据契约，再补 UI 细节
- 先做垂直切片，再做大范围重构
- 不把 roadmap feature 当成已存在接口

## 9. 稳定契约

以下契约是后续开发默认遵循的稳定方向。新增实现时优先兼容这些约定。

### 9.1 SSE 事件契约

目标事件类型：

- `metadata`
- `token`
- `progress`
- `artifact`
- `error`
- `done`

### 9.2 统一产物对象契约

后续所有产物生成结果统一抽象为 artifact，包含：

```ts
type Artifact = {
  id: string | number
  type: "ppt" | "docx" | "html-game" | "pdf" | "other"
  title: string
  status: "pending" | "running" | "ready" | "failed"
  mime_type?: string
  storage_path?: string
  url?: string
  preview_url?: string
  plan_id?: number
  thread_id?: string
}
```

### 9.3 统一进度步骤对象契约

后续所有流程卡片统一抽象为 progress step，至少包含：

```ts
type ProgressStep = {
  step_key: string
  label: string
  status: "pending" | "running" | "success" | "failed"
  detail?: string
  started_at?: string
  finished_at?: string
}
```

要求：

- `step_key` 应能映射到 graph 节点或明确的子任务
- 前后端都不应各自定义一套完全不同的步骤语义

## 10. 变更验收清单

### 后端

- API schema 是否同步更新
- graph 是否接入新状态或新节点
- 文件处理链路是否与 `knowledge_files` / `attachments` 正确对应
- 失败状态是否可追踪、可返回

### 前端

- 消息渲染是否兼容旧事件与新事件
- 进度卡片是否来自真实后端事件
- 产物展示是否接入统一 artifact 模型
- 回退兼容是否保留

## 11. 协作建议

- 开工前先读本文件，再读对应模块入口文件
- 对话、进度、产物、附件这四类能力优先看成“协议问题”，其次才是 UI 问题
- 需求不明确时，优先做对后续演进最稳的抽象，不做一次性特判
- 任何新增功能都应说明：属于哪条链路、复用了哪些已有能力、输出遵循什么契约

由于沙盒环境和路径问题，你需要直接使用绝对路径读取代码。
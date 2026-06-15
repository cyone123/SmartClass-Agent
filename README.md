# SmartClass Agent

<div align="center">

**🎓 面向教师的智能教学助手**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)](https://github.com/langchain-ai/langgraph)
[![Vue](https://img.shields.io/badge/Vue-3.5+-42b883.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*基于 LangGraph 的多模态教学智能体，帮助教师快速完成备课、教学设计、课件生成与互动内容创作*

[功能特性](#功能特性) • [快速开始](#快速开始) • [架构设计](#架构设计) • [文档](#文档) • [贡献指南](#贡献指南)

</div>

---

## 📖 项目简介

SmartClass Agent 是一个专为教师设计的智能教学助手，通过对话式交互帮助教师完成从教学设计到课件生成的全流程工作。系统基于 LangGraph 构建了多节点 Agent 工作流，支持意图识别、RAG 检索、教学设计、产物生成等能力，并提供长期记忆、版本管理、差量修改等高级特性。

### 🎯 核心价值

- **💬 对话式交互**：自然语言描述教学需求，Agent 自动理解并生成内容
- **🎨 多模态输入**：支持文本、图片、语音、视频等多种输入方式
- **📚 知识库增强**：RAG 检索个人教学资料，生成个性化教学内容
- **🔄 版本管理**：产物支持多次迭代修改，保留完整版本链
- **🧠 长期记忆**：记住教师偏好和教学经验，持续优化生成效果

### 🚀 典型工作流

```mermaid
graph LR
    A[教师输入需求] --> B[意图识别]
    B --> C{需求类型}
    C -->|教学设计| D[提取教学要素]
    C -->|产物修改| E[识别修改目标]
    D --> F[RAG 检索知识库]
    F --> G[生成教学设计]
    G --> H[并行生成产物]
    H --> I[PPT 课件]
    H --> J[DOCX 教案]
    H --> K[HTML 互动内容]
    E --> L[加载当前版本]
    L --> M[差量修改]
    M --> N[生成新版本]
```

---

## ✨ 功能特性

### 🎓 教学内容生成

- **教学设计**：根据学科、年级、主题自动生成教学目标、重难点、教学方法
- **课件生成**：自动生成 PowerPoint 课件（.pptx），支持标题页、目录页、内容页、总结页
- **教案生成**：自动生成 Word 教案（.docx），包含完整的教学流程和活动设计
- **互动内容**：生成 HTML 互动小游戏、演示页面，提升课堂参与度

### 🔍 智能检索与分析

- **RAG 向量检索**：基于 PGVector 的知识库检索，支持 PDF、DOCX、TXT 等格式
- **附件分析**：自动分析图片、文档内容，提取关键信息融入教学设计
- **视频转写**：抽取视频音频、转写文本、提取关键帧、生成画面描述

### 🧠 长期记忆系统

- **用户画像**：记忆教师背景、教学风格、学生特点
- **经验积累**：记录成功的教学案例、学生反馈、效果评价
- **语义检索**：根据当前话题智能召回相关经验，辅助决策

### 🔄 产物迭代管理

- **差量修改**：基于当前版本进行局部调整，保留原有内容
- **版本链追溯**：完整记录修改历史，支持版本回退
- **多产物并行**：同时生成 PPT、DOCX、HTML，独立修改互不干扰

### 🛡️ 安全与可控

- **Workspace 隔离**：每次执行独立工作区，防止路径遍历和数据泄露
- **代码执行限制**：超时、输出截断、依赖拦截，确保安全
- **资源归属校验**：所有资源按用户隔离，严格权限控制

### 📊 可观测性

- **结构化日志**：关联 `run_id`、`thread_id`、`user_id`，支持全链路追踪
- **JSONL Trace**：每日归档，便于离线分析
- **Prometheus 指标**：请求量、错误率、响应时间、Token 消耗
- **OpenTelemetry**：分布式追踪，集成 Jaeger、Zipkin、Honeycomb

---

## 🏗️ 架构设计

### 技术栈

**后端**
- **框架**：FastAPI + Uvicorn
- **Agent**：LangChain + LangGraph
- **数据库**：PostgreSQL + PGVector
- **存储**：Local / MinIO 对象存储
- **认证**：JWT Bearer
- **可观测**：OpenTelemetry + Prometheus

**前端**
- **框架**：Vue 3 + Vite
- **UI 组件**：Element Plus
- **状态管理**：Pinia
- **文件预览**：OnlyOffice Document Editor
- **实时通信**：SSE (Server-Sent Events)

### 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                        Frontend                         │
│  Vue 3 + Element Plus + Pinia + OnlyOffice             │
└────────────────┬────────────────────────────────────────┘
                 │ SSE Events (metadata, token, progress, artifact)
                 │ REST API (auth, file, memory, session)
┌────────────────┴────────────────────────────────────────┐
│                      FastAPI Backend                    │
│  ┌──────────────────────────────────────────────────┐  │
│  │            LangGraph Agent Workflow              │  │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────────┐    │  │
│  │  │ Intent  │→ │ Metadata│→ │ RAG Retrieval│    │  │
│  │  │ Router  │  │ Extract │  │              │    │  │
│  │  └─────────┘  └─────────┘  └──────────────┘    │  │
│  │       ↓             ↓              ↓             │  │
│  │  ┌─────────────────────────────────────────┐   │  │
│  │  │      Teaching Design Planner            │   │  │
│  │  └─────────────────────────────────────────┘   │  │
│  │       ↓             ↓              ↓             │  │
│  │  ┌──────┐      ┌──────┐      ┌──────────┐     │  │
│  │  │ PPT  │      │ DOCX │      │   HTML   │     │  │
│  │  │ Gen  │      │ Gen  │      │   Game   │     │  │
│  │  └──────┘      └──────┘      └──────────┘     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  PostgreSQL  │  │   PGVector   │  │  LangGraph   │ │
│  │  (业务数据)  │  │  (向量索引)  │  │  Store       │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   MinIO /    │  │  Workspace   │  │ Observability│ │
│  │   Local FS   │  │  (隔离执行)  │  │ (日志/指标)  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| **认证权限** | `app/core/auth.py` | JWT 认证、密码哈希、用户归属校验 |
| **存储服务** | `app/core/storage.py` | 统一存储抽象，支持 Local/MinIO |
| **对话流程** | `app/core/graph.py` | LangGraph 主流程，60+ KB |
| **Agent Runtime** | `app/core/agent.py` | Agent 执行、工具集成，91 KB |
| **长期记忆** | `app/core/memory.py` | Profile/Experience 记忆管理 |
| **RAG 检索** | `app/core/rag.py` | 向量检索、文档分块 |
| **Workspace** | `app/core/workspace.py` | 隔离工作区、代码执行，43 KB |
| **可观测性** | `app/core/observability.py` | 日志、指标、Trace，40 KB |

---

## 🚀 快速开始

### 前置要求

- **Python** 3.11+
- **Node.js** 20.19+ 或 22.12+
- **PostgreSQL** 14+（已安装 PGVector 扩展）
- **可选**：MinIO（对象存储）、Prometheus（指标监控）

### 1. 克隆仓库

```bash
git clone --recurse-submodules https://github.com/cyone123/SmartClass-Agent.git
cd SmartClass-Agent
```

如果已经克隆过主仓库：

```bash
git submodule update --init --recursive
```

### 2. 后端设置

#### 安装依赖

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 配置环境变量

复制 `.env.local.example` 到 `.env` 并修改：

```bash
cp .env.local.example .env
```

**核心配置：**

```env
# 数据库
DATABASE_URL=postgresql://user:password@localhost:5432/smartclass

# LLM API (OpenAI 兼容)
MODEL=your-model-name
API_KEY=your-api-key
BASE_URL=your-base-url

# JWT 密钥（生产环境必须修改）
JWT_SECRET_KEY=your-secret-key-change-in-production

# 存储后端（local 或 minio）
STORAGE_BACKEND=local
FILE_STORAGE_ROOT=../storage

# 可选：MinIO 对象存储
# STORAGE_BACKEND=minio
# MINIO_ENDPOINT=localhost:9000
# MINIO_ACCESS_KEY=minioadmin
# MINIO_SECRET_KEY=minioadmin
# MINIO_BUCKET=smartclass

# 可选：可观测性
OBSERVABILITY_ENABLED=true
OBSERVABILITY_TRACE_JSONL_ENABLED=true
PROMETHEUS_ENABLED=false
OTEL_ENABLED=false
```

#### 初始化数据库

```bash
# 创建数据库和扩展
psql -U postgres -c "CREATE DATABASE smartclass;"
psql -U postgres -d smartclass -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 启动后端

```bash
python run_server.py
```

后端将运行在 `http://localhost:8000`

### 3. 前端设置

#### 安装依赖

```bash
cd frontend
npm install
```

#### 启动前端

```bash
npm run dev
```

前端将运行在 `http://localhost:5173`

### 4. 访问应用

打开浏览器访问 `http://localhost:5173`

**默认账号**（首次启动自动创建）：
- 用户名：`admin`
- 密码：`admin12345`

### 5. 上传知识库（可选）

1. 登录后进入"知识库管理"
2. 上传教学资料（PDF、DOCX、TXT）
3. 等待索引完成（状态变为"已就绪"）
4. 在对话中 Agent 将自动检索相关内容

---

## 🐳 Docker 部署

### 使用 Docker Compose（推荐）

```bash

# 准备环境文件：
cp .env.docker.example .env.docker

# 构建并启动所有服务
docker compose --env-file .env.docker up -d --build

# 停止服务
docker compose --env-file .env.docker down
```

**服务访问：**
- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- Prometheus：`http://localhost:9090`
- MinIO：`http://localhost:9000`

---

## 🔧 开发指南

### 项目结构

```
smartclass-agent/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心模块（graph, agent, memory...）
│   │   ├── models/         # SQLAlchemy 模型
│   │   ├── services/       # 业务逻辑层
│   │   └── schemas/        # Pydantic 模型
│   ├── skills/             # Skill 定义
│   ├── storage/            # 文件存储（本地模式）
│   ├── tests/              # 单元测试
│   └── run_server.py       # 启动脚本
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── api/           # API 调用
│   │   ├── components/    # Vue 组件
│   │   ├── store/         # Pinia 状态
│   │   └── views/         # 页面
│   └── vite.config.js
├── docs/                   # 模块文档
├── docker-compose.yml      # Docker Compose 配置
├── CLAUDE.md               # AI 开发规范
└── README.md
```

### 添加新功能

1. **定义数据模型**：`backend/app/models/`
2. **实现业务逻辑**：`backend/app/services/`
3. **添加 API 路由**：`backend/app/api/`
4. **集成 LangGraph 节点**：`backend/app/core/graph.py`
5. **前端界面开发**：`frontend/src/views/`

### 运行测试

```bash
cd backend
pytest tests/
```

### 代码风格

**Python：**
- 使用 `black` 格式化
- 遵循 PEP 8 规范
- 类型注解（Type Hints）

**Vue：**
- 使用 `<script setup>` 语法
- Composition API
- 遵循 Vue 3 风格指南

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. **Fork 本仓库**
2. **创建特性分支** (`git checkout -b feature/amazing-feature`)
3. **提交更改** (`git commit -m 'Add amazing feature'`)
4. **推送到分支** (`git push origin feature/amazing-feature`)
5. **创建 Pull Request**

### 贡献类型

- 🐛 **Bug 修复**：提交 Issue 并附上复现步骤
- ✨ **新功能**：先在 Issue 讨论设计方案
- 📝 **文档改进**：修正错误、补充示例
- 🎨 **UI/UX 优化**：改进用户体验
- 🧪 **测试覆盖**：增加单元测试、集成测试

### 开发约定

- **提交信息**：遵循 Conventional Commits
  - `feat:` 新功能
  - `fix:` Bug 修复
  - `docs:` 文档更新
  - `refactor:` 代码重构
  - `test:` 测试相关
- **代码审查**：所有 PR 需至少一人审查
- **测试要求**：核心功能需有测试覆盖

---

## 📋 路线图

### v1.0（已完成）✅
- [x] 基础对话流程
- [x] 教学设计生成
- [x] PPT/DOCX/HTML 产物生成
- [x] 知识库 RAG 检索
- [x] 长期记忆系统
- [x] 产物版本管理

### v1.1（进行中）🚧
- [ ] 评估数据集构建
- [ ] Grafana 仪表盘模板
- [ ] 多语言支持（英文）

### v2.0（规划中）📝
- [ ] 多模型支持（Claude、Gemini、Qwen）
- [ ] 协作编辑（多教师共享知识库）
- [ ] 移动端适配
- [ ] 插件系统
- [ ] SaaS 部署方案

---

## 🙏 致谢

SmartClass Agent 基于以下优秀的开源项目构建：

- [LangChain](https://github.com/langchain-ai/langchain) - LLM 应用框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent 状态图编排
- [FastAPI](https://github.com/tiangolo/fastapi) - 现代 Python Web 框架
- [Vue.js](https://github.com/vuejs/core) - 渐进式前端框架
- [PostgreSQL](https://www.postgresql.org/) - 开源关系型数据库
- [PGVector](https://github.com/pgvector/pgvector) - PostgreSQL 向量扩展

特别感谢所有贡献者的付出！

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

---

## 📧 联系我们

- **Issue Tracker**：[GitHub Issues](https://github.com/cyone123/SmartClass-Agent/issues)
- **讨论区**：[GitHub Discussions](https://github.com/cyone123/SmartClass-Agent/discussions)
- **邮件**：zsh.xyz@foxmail.com

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给我们一个 Star！**

Made with ❤️ by SmartClass Team

</div>

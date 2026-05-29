# SmartClass 用户认证与资源归属设计规范

- 日期：2026-06-01
- 范围：用户注册 / 登录 / JWT access token / 默认管理员承接历史数据 / 资源归属权限
- 状态：草案

## 1. 背景与目标

SmartClass 当前已具备教学计划、会话、知识库文件、附件、产物、SSE 流式聊天和 Agent 执行链路，但整体仍以“单租户共享数据”为默认前提。随着项目进入工程化增强阶段，需要先补齐基础身份认证，再把所有可见资源纳入用户边界。

本次设计的目标是建立一套适合当前 FastAPI + Vue 架构的基础认证体系：

- 支持开放注册
- 支持用户名/密码登录
- 只使用 JWT access token
- 将历史计划、会话、文件与产物统一归属到默认管理员用户
- 所有业务资源都按 `user_id` 进行隔离
- 默认管理员 `admin` 不拥有跨用户查看或管理资源的全局权限

本次不包含：

- refresh token
- 第三方登录
- 完整 RBAC 体系
- 管理后台
- 审批流之外的复杂授权模型

## 2. 设计原则

1. **先认证，再隔离**：先确认“是谁”，再确认“能访问什么”。
2. **默认最小权限**：注册用户默认是普通教师角色，只能访问自己的数据。
3. **资源归属优先**：所有计划、会话、文件、产物都必须能落到明确的 `user_id`。
4. **不引入过早复杂度**：第一版只做 access token，不做 refresh token。
5. **历史数据可追溯**：历史记录必须可回填到默认管理员用户，不能保留“无主数据”。
6. **admin 不越权**：`admin` 仅是系统初始账号和历史数据承接账号，不是全局超级管理员。

## 3. 方案选择

### 3.1 采用方案

推荐采用：**JWT access token + 资源归属校验 + 最小角色字段**。

#### 理由

- 与当前 FastAPI 架构契合
- 实现复杂度可控
- 易于按路由和服务层逐步改造
- 能直接覆盖当前最重要的安全风险：跨用户访问

### 3.2 不采用的方案

#### 方案 A：只做登录，不做资源隔离
- 优点：最快
- 缺点：安全风险高，不能满足项目目标

#### 方案 B：JWT + refresh token + 完整 RBAC
- 优点：更完整
- 缺点：当前阶段过重，容易把认证问题做成权限平台项目

### 3.3 结论

第一版选择 **JWT access token-only**，并在数据层和服务层统一补充 `user_id` 过滤。

## 4. 身份与角色模型

### 4.1 用户模型

新增 `users` 表，字段建议如下：

- `id`
- `username`
- `password_hash`
- `display_name`
- `role`
- `is_active`
- `is_superuser`
- `created_at`
- `updated_at`

### 4.2 角色定义

第一版只保留两个角色语义：

- `teacher`：默认注册用户
- `admin`：系统默认管理员账号，仅用于初始化和历史数据承接

这里的 `admin` **不是全局超级管理员**。它和普通用户一样，只能访问自己的资源。

### 4.3 密码存储

密码必须使用哈希存储，不允许明文落库。推荐使用 bcrypt 哈希方案。

## 5. JWT 设计

### 5.1 令牌类型

第一版仅使用 **access token**。

### 5.2 令牌载荷

建议包含以下字段：

- `sub`：用户 ID
- `username`：用户名
- `role`：角色
- `exp`：过期时间

### 5.3 过期策略

第一版建议使用较长但有限的过期时间，例如 24 小时，后续可根据实际体验再调整。

### 5.4 前端存储

前端使用 `localStorage` 或 `sessionStorage` 保存 access token，并在请求头中统一附带：

```http
Authorization: Bearer <token>
```

## 6. 权限控制模型

### 6.1 第一层：是否已登录

所有受保护接口都要求 JWT 有效。

### 6.2 第二层：是否归属当前用户

所有业务资源都必须与当前用户存在明确归属关系。校验规则统一为：

```text
resource.user_id == current_user.id
```

### 6.3 第三层：角色字段的用途

本次设计中，角色字段只用于未来扩展与初始账号标识，不用于跨用户授权。

即：

- `admin` 不可查看其他用户资源
- `teacher` 不可查看其他用户资源
- 两者的访问规则一致
- 唯一差异是历史数据默认归 `admin` 所有

## 7. 资源归属范围

以下资源必须补充 `user_id`：

- 教学计划 `teaching_plans`
- 教学会话 `teaching_sessions`
- 知识库文件 `knowledge_files`
- 会话附件 `attachment_files`
- 产物文件 `artifact_files`

### 7.1 为什么建议直接加 `user_id`

虽然部分资源可以通过 `plan_id` 或 `thread_id` 间接归属到用户，但第一版仍建议每张核心表都直接保存 `user_id`，原因是：

- 查询更简单
- 归属校验更直接
- 迁移和排查更容易
- 避免依赖链过长导致漏校验

## 8. 历史数据回填策略

现有计划、会话、知识库文件、附件文件和产物文件都需要回填到默认管理员用户。

### 8.1 回填顺序

1. 创建默认管理员用户 `admin`
2. 回填教学计划 `user_id`
3. 回填会话 `user_id`
4. 回填知识库文件 `user_id`
5. 回填附件文件 `user_id`
6. 回填产物文件 `user_id`

### 8.2 回填结果

回填后：

- 老数据可继续访问
- 所有历史记录都拥有明确 owner
- 新注册用户只会拥有自己创建的数据

### 8.3 默认管理员定位

默认管理员账号仅承担：

- 历史数据 owner
- 系统初始可登录账号

不承担：

- 跨用户查看权限
- 跨用户管理权限
- 额外的超级管理员能力

## 9. API 设计

### 9.1 注册

`POST /api/auth/register`

请求示例：

```json
{
  "username": "teacher001",
  "password": "12345678",
  "display_name": "王老师"
}
```

响应示例：

```json
{
  "id": 1,
  "username": "teacher001",
  "display_name": "王老师",
  "role": "teacher"
}
```

约束：

- 用户名唯一
- 密码长度至少 8 位
- 不能注册为 `admin`
- 默认角色为 `teacher`

### 9.2 登录

`POST /api/auth/login`

请求示例：

```json
{
  "username": "teacher001",
  "password": "12345678"
}
```

响应示例：

```json
{
  "access_token": "jwt...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "username": "teacher001",
    "display_name": "王老师",
    "role": "teacher"
  }
}
```

### 9.3 当前用户

`GET /api/auth/me`

返回当前 JWT 对应的用户信息。

### 9.4 登出

第一版不提供服务端登出。前端删除本地 token 即视为登出。

## 10. 后端实现边界

建议新增以下模块：

- `backend/app/api/auth.py`
- `backend/app/core/auth.py`
- `backend/app/models/user.py`
- `backend/app/schemas/auth.py`
- `backend/app/services/auth_service.py`

建议改造以下模块：

- `backend/app/main.py`：挂载 auth router
- `backend/app/dependencies/db.py`：配合初始化与迁移逻辑
- `backend/app/api/plan.py`
- `backend/app/api/session.py`
- `backend/app/api/chat.py`
- `backend/app/api/file.py`
- `backend/app/services/plan_service.py`
- `backend/app/services/session_service.py`
- `backend/app/services/file_service.py`
- `backend/app/services/artifact_service.py`

### 10.1 认证依赖

需要一个统一的 `get_current_user` 依赖：

1. 读取 `Authorization` 头
2. 解析 JWT
3. 取出 `sub`
4. 查询用户
5. 校验用户是否存在且可用
6. 返回当前用户对象

### 10.2 资源校验依赖

建议为高风险资源提供统一的“owner 校验”函数，例如：

- `get_owned_plan`
- `get_owned_session`
- `get_owned_file`
- `get_owned_artifact`

这些依赖负责把“是否属于当前用户”作为服务端强约束。

## 11. 前端实现边界

建议新增或调整以下内容：

- 登录\注册弹窗界面
- auth store
- token 注入拦截器
- 路由守卫

建议改造：

- `frontend/src/api/index.js`
- `frontend/src/router/index.js`
- `frontend/src/store/user.js`

### 11.1 前端请求策略

请求统一从 store 读取 token，并自动放入 `Authorization` 头。

### 11.2 路由策略

未登录用户执行创建计划、会话等操作时弹出登录弹窗。

### 11.3 401 处理

当接口返回 401 时：

- 清理本地 token
- 弹出登录弹窗
- 重新拉取用户态时重置前端状态

## 12. 关键链路改造

### 12.1 `/api/chat/stream`

聊天流接口必须先完成认证，再做资源归属判断：

- `thread_id` 必须属于当前用户的会话
- `attachment_ids` 必须属于当前用户
- 不能通过猜测 `thread_id` 访问其他用户上下文

### 12.2 文件预览与下载

所有预览、下载接口必须先校验 owner，再返回文件路径、URL 或代理流。

### 12.3 产物访问

产物列表、预览、下载和 revision 历史都必须按 `user_id` 过滤。

### 12.4 计划和会话列表

计划和会话列表必须按当前用户过滤，避免全局可见。

## 13. 错误处理约定

### 13.1 401 Unauthorized

用于：

- token 缺失
- token 无效
- token 过期
- 当前用户不存在

### 13.2 404 Not Found

用于：

- 资源不存在
- 资源不属于当前用户

优先使用 404 而不是 403，以减少资源存在性泄露。

### 13.3 400 Bad Request

用于：

- 用户名非法
- 密码过短
- 请求参数缺失
- 注册格式不合法

## 14. 数据迁移与初始化策略

当前项目已存在启动期补丁式 schema 初始化逻辑，因此认证功能第一版可以先延续该风格，但必须把用户表和 `user_id` 字段补齐。

### 14.1 初始化任务

应用启动时需要：

- 创建用户表
- 创建默认管理员用户（如不存在）
- 补齐历史数据 owner
- 保证新增字段与现有数据兼容

### 14.2 兼容要求

迁移必须满足：

- 不能破坏现有计划、会话、文件和产物的可读性
- 不能让历史数据变成无 owner 状态
- 不能依赖手工 SQL 才能启动系统

## 15. 安全边界

### 15.1 必须做的事

- 密码哈希存储
- JWT 校验
- 所有资源查询都加 owner 约束
- 文件预览和下载前校验归属
- chat stream 中校验 thread / attachment 归属

### 15.2 不做的事

- 不做跨用户后台管理
- 不做 refresh token
- 不做 token 黑名单
- 不做“admin 看全部”的后门

## 16. 测试策略

第一版至少需要覆盖以下用例：

### 16.1 认证

- 注册成功
- 用户名重复注册失败
- 密码过短注册失败
- 登录成功
- 密码错误登录失败
- 过期或无效 token 访问受保护接口失败

### 16.2 资源归属

- 用户 A 不能访问用户 B 的教学计划
- 用户 A 不能访问用户 B 的会话
- 用户 A 不能访问用户 B 的文件
- 用户 A 不能访问用户 B 的产物

### 16.3 历史数据

- 历史记录能成功回填到默认管理员用户
- 回填后历史资源仍可正常查询

### 16.4 关键链路

- `/api/chat/stream` 不能接受不属于当前用户的 thread
- 文件预览 / 下载不能绕过 owner 校验

## 17. 风险与注意事项

1. **最容易漏改的是详情接口，不是列表接口。**
2. **文件下载和预览最容易绕过归属校验。**
3. **chat stream 的 `thread_id` 风险高，必须严查归属。**
4. **历史数据回填必须完整，不能只改部分表。**
5. **`admin` 不应被误实现成超级管理员。**

## 18. 结论

第一版认证方案定为：

- 用户名/密码注册登录
- JWT access token
- 默认管理员承接历史数据
- 所有核心资源按 `user_id` 隔离
- `admin` 不拥有跨用户权限

这是一套适合当前 SmartClass 阶段的最小闭环方案，能够先把“谁能登录”和“谁能看什么”两个核心问题稳定下来。

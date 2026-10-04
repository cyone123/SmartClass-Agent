# 多提供商模型运行时配置

SmartClass 将协议、提供商预设、连接、模型 Profile 与业务角色分开配置。当前支持
`openai_chat`、`anthropic_messages`、`google_genai` 三种协议；提供 OpenAI、Anthropic、
Gemini、OpenRouter、DeepSeek、智谱与 custom 预设。模型 ID 不会改变所选协议。

## 配置入口

复制根目录 `model-config.example.yaml`，在根目录 `.env` 中设置：

```env
MODEL_CONFIG_PATH=model-config.yaml
API_KEY=replace-at-deployment
```

Windows 相对路径以仓库根目录解析，也可使用绝对路径。配置在进程启动时加载；修改 YAML 后需
重启后端。Docker Compose 将示例只读挂载为 `/app/config/model-config.yaml`，在
`.env.docker` 中设置该容器路径即可启用。

YAML 显式角色优先于旧环境变量。一个角色只允许选择完整 model，或完整继承另一个角色；只填写
`MODEL`、只填写 key、或尝试从其他角色借 endpoint/key 都会给出字段级错误。未迁移部署仍可使用
完整的 legacy 三元组。`compression`、`video_vision` 等可选角色禁用时不要求其凭据。

凭据只能写成 `env:NAME` 引用。轮换该环境变量后，后续调用会使用新值，但已固定工作流的 provider、
protocol、endpoint、model 与参数策略不变。引用缺失或撤销时调用明确失败，不会借用另一个角色或账号。

## 存储扩展接口

运行时只依赖同步 `ConfigRepository.load() -> ResolvedModelConfigSnapshot`，不依赖 File/Env 的实现细节。
`FileConfigRepository`、`EnvConfigRepository` 和测试用 `InMemoryConfigRepository` 实现同一接口。
未来 Database repository 可在不修改 Graph、Agent、Memory、Compression 调用方的情况下替换它；
密钥仍由独立 `SecretResolver` 在调用边界解析。本期不提供配置管理 API 或前端页面。

公开 DTO 仅用于展示安全身份和能力状态，例如：

```json
{
  "version": 1,
  "fingerprint": "v1:<sha256>",
  "rules_version": "1",
  "roles": {"main": {"enabled": true, "model": "teaching"}},
  "models": {
    "teaching": {
      "model_id": "vendor/model",
      "protocol": "openai_chat",
      "provider": "openrouter",
      "verification": "declared",
      "verified": false
    }
  }
}
```

DTO 和评估证据不包含 endpoint、credential reference、密钥、header、prompt、completion、推理正文、
对象 key 或宿主机路径。聚合器无法返回实际上游时记录 `unknown`，不会从模型 ID 推断。

## 验证层级

- 默认 pytest 使用确定性 fixture，证明配置、协议转换和业务编排，不证明真实 provider 可用或效果。
- `tests.provider_smoke` 是独立的 live smoke，缺凭据必须记为 `unverified`，不能计为通过。
- 业务 eval 保留 `PASSED`、`FAILED`、`ERROR`、`pass_rate` 与 `avg_score`；只有通过 fail-closed
  回归门禁的 schema 2.0 报告才可晋升 baseline。

发布与回滚步骤见 [模型运行时发布与回滚](deployment/model-runtime-release.md)。

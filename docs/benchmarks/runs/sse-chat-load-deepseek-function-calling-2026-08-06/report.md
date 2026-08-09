# SSE 非 RAG 压测报告：DeepSeek function calling

日期：2026-08-06

## 兼容性改动

DeepSeek 结构化模型现在自动使用：

- `with_structured_output(..., method="function_calling", include_raw=True)`；
- 不传 `strict`；
- `ChatOpenAI(..., extra_body={"thinking": {"type": "disabled"}})`。

其他模型仍保持 `method="json_schema"`、`strict=True`。真实结构化 warmup 返回
`ConversationRoute`，且 `parsing_error=None`，之后才启动压测。

## 压测结果

本轮只压认证后的 `/api/chat/stream`，固定普通聊天提示词，不进入教学设计、RAG、附件或产物分支。

| 并发用户 | 完整流尝试 | 失败 | 完整流失败率 | 完整流耗时 p50/p95 | TTFT 成功样本 | TTFT p50/p95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 7 | 0 | 0% | 8.3s / 12.0s | 7 | 2.2s / 4.8s |
| 2 | 18 | 0 | 0% | 5.9s / 12.0s | 18 | 1.8s / 2.5s |
| 4（第一次） | 33 | 0 | 0% | 7.2s / 11.0s | 32 | 1.8s / 3.1s |
| 4（重复） | 35 | 0 | 0% | 6.9s / 11.0s | 33 | 1.9s / 2.6s |
| 8 | 68 | 0 | 0% | 6.7s / 10.0s | 67 | 1.9s / 2.7s |

5 次 smoke 请求也全部成功，错误事件计数为 0。1/2/4/8 路正式阶段共完成 161 次完整流，
失败率为 0%。

压测结束时后端进程工作集约 373.95MB、私有内存约 729.41MB；这是单次结束快照，不是峰值采样。

## 对比上一轮 DeepSeek json_schema

上一轮同类 DeepSeek 主模型压测中，8 路失败率为 30%；本轮切换为
`function_calling + thinking disabled` 后，8 路 68/68 完整成功，失败率降为 0%。
本轮所有阶段都未产生 SSE `error` 事件。

这说明上一轮失败主要来自结构化输出请求兼容性，而不是单纯的 SSE 并发容量问题；
但本轮仍是单实例、真实模型、60 秒窗口，不能直接宣称生产容量或长期 SLO。

## 结论

兼容性修复已通过真实结构化输出验证，并在本轮 1～8 路短时压测中保持完整流 100%。
结果可作为候选性能证据，但正式晋升 baseline 仍需多轮 5 分钟窗口、Mock LLM 对照和资源峰值采样。
`resume.md` 本轮暂未修改。

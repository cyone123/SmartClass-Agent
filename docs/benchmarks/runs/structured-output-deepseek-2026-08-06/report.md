# DeepSeek 结构化输出兼容性实验

日期：2026-08-06

## 改动

在 `app/core/graph.py` 中增加了 provider 判断：当结构化模型是 DeepSeek 时，
`with_structured_output` 只传 `include_raw=True`，不显式传 `method` 和 `strict`；
其他模型仍使用原来的 `method="json_schema"`、`strict=True`。

## 实验结果

| 实验 | 配置 | 结果 |
| --- | --- | --- |
| graph 默认方式 | 不传 `method`/`strict` | 失败：`400 response_format type is unavailable now` |
| 显式 function calling | `method="function_calling"` | 失败：`400 Thinking mode does not support this tool_choice` |
| 兼容性对照 | `function_calling` + `thinking=disabled` | 成功，解析为 `ConversationRoute` |

成功样例解析结果：

```json
{
  "intent": "normal_chat",
  "artifact_targets": [],
  "needs_clarification": false
}
```

## 结论

仅省略 `method` 和 `strict` 没有解决问题，因为当前 LangChain 版本的 provider 默认仍然
发送 `json_schema` response format。按用户指定的模式，结构化输出门禁未通过，因此本轮
没有启动压测。

实验同时证明了一个可行候选：DeepSeek 使用 `function_calling`，并显式关闭 thinking。
这需要改变当前结构化模型的 provider-specific 配置，超出本轮“只省略 method/strict”的范围，
暂未写入生产逻辑。

后续已按该候选组合完成实现和压测，详见 [SSE 压测报告](../sse-chat-load-deepseek-function-calling-2026-08-06/report.md)。

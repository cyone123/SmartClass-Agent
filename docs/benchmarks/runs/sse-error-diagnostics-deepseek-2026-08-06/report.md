# SSE error 事件原因诊断报告：DeepSeek

日期：2026-08-06

## 为什么现在能看到原因

之前压测脚本只记录 `error=True`，没有读取 SSE `data`。现在脚本会：

1. 解析 `error` 事件 JSON；
2. 提取 `category`、`error_type`、`message`；
3. 对凭据、URL 查询参数和本地路径脱敏，并限制摘要长度；
4. 将低基数原因计数写入 `SMARTCLASS_BENCHMARK_OUTPUT` 的 `error_reasons`；
5. 将分类追加到 Locust failure CSV，但不保存原始错误正文。

## 本次复现结果

本次使用 8 路、60 秒、DeepSeek 主模型，结构化输出配置为
`STRUCTURED_METHOD=json_schema`、`strict=true`：

| 指标 | 结果 |
| --- | ---: |
| SSE 尝试 | 1,022 |
| SSE 失败 | 1,019（99.71%） |
| HTTP 非 200 | 0 |
| 捕获到的 error 事件 | 1,019 |

所有失败均归并到同一原因：

| 数量 | 分类 | provider 类型 | 脱敏后的原因 |
| ---: | --- | --- | --- |
| 1,019 | `unsupported_response_format` | `invalid_request_error` | `Error code: 400 — This response_format type is unavailable now` |

## 结论

这轮已经排除“HTTP 连接失败”这一方向；错误是 DeepSeek 对结构化输出请求参数的 400 拒绝，
具体涉及 `response_format` 类型不可用。它不是当前证据下的限流错误。

由于错误返回很快，Locust 用户在 60 秒内快速重试，导致 1,022 次尝试；这组数据只能用于
错误定位，不能拿来当并发容量基线。

代码位置：

- `backend/tests/benchmarks/sse_protocol.py`：脱敏、分类和 provider 错误类型提取；
- `backend/tests/benchmarks/sse_load.py`：汇总 `error_reasons` 并把分类写入失败 CSV。

下一步应先验证 DeepSeek 是否支持 `function_calling` 结构化输出，或为 DeepSeek 禁用/替换
`json_schema` 路径，再重新做容量压测；不要直接把本轮失败率写入简历。

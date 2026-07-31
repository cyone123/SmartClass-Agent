# 阶段 1：真实模型评估基线

日期：2026-07-30

## 结论

最终全量评估通过回归门禁并晋升为 `stage1-model-eval-2026-07-30`：

- 24 个用例中 23 个通过，整体通过率 **95.83%**
- 20 个真实模型用例，4 个确定性上下文压缩用例
- 0 个运行时错误，错误率 **0%**
- 用例平均分 **0.942**
- Suite 总耗时 **575.75 秒**

该结果来自测试/benchmark，不代表生产流量或线上 SLA。

## 分类结果

| 分类 | 模式 | 通过 | 通过率 | 平均分 |
| --- | --- | ---: | ---: | ---: |
| Intent Recognition | model-eval | 5/5 | 100% | 1.000 |
| Extraction Quality | model-eval | 6/7 | 85.71% | 0.801 |
| Memory Retrieval | model-eval | 3/3 | 100% | 1.000 |
| Memory Write | model-eval | 4/4 | 100% | 1.000 |
| Memory Update | model-eval | 1/1 | 100% | 1.000 |
| Context Compression | deterministic | 4/4 | 100% | 1.000 |

唯一未通过用例为歧义表达“为数学年级设计关于微积分的课程”：路由正确，但一次结构化抽取未提取出明确出现的“数学”。该失败作为模型波动和后续回归样本保留，没有通过降低断言标准消除。

## 环境与复现信息

- Provider：DashScope
- Main model：`qwen3.7-max-2026-06-08`
- Structured/Fast/Small/Memory model：`qwen3.7-flash-2026-07-15`
- OS：Windows 11，AMD64
- Python：3.13.0
- 数据集指纹：`sha256:fc363adfca72397f2af3bdd4350d2e0ac6ed524f140154deb674a902a9487a53`
- 源码指纹：`sha256:f34d4e7a3830f427307691c89bcbbde9a85d6ab787f2855f3be45dc1533ae235`
- Git HEAD：`961f007c9d2b976b7c7f3e6b1df1e27ceab6dda8`
- 工作树状态：dirty；正式报告通过源码指纹覆盖未提交改动

运行命令：

```bash
python -m tests.evals.cli validate-suite --expected-count 24
python -m tests.evals.cli run --local-docker-db --verbose
python -m tests.evals.check_regression \
  --report tests/evals/results/eval_1785428042.json
python -m tests.evals.cli promote-baseline \
  --report tests/evals/results/eval_1785428042.json \
  --baseline-id stage1-model-eval-2026-07-30
```

## 评估驱动修复

真实运行暴露并修复了以下问题：

1. evaluator 未注入 YAML 中声明的 chat history 与 artifact catalog，导致产物修改意图误判。
2. evaluator 未像生产链路一样传递 LangGraph runtime `user_id`，造成记忆 namespace 与 Graph 读取用户不一致。
3. 普通聊天和教学规划路由绕过了已注册的经验记忆检索节点。
4. 经验标题与当前请求完全匹配时仍依赖模型选择，增加波动；新增确定性精确标题快路径。
5. Profile 反思器会把天气闲聊和一次性敏感班级背景写入长期记忆；新增写入资格门与确定性脱敏。
6. 结构化快速模型返回空对象时没有触发可靠模型 fallback。
7. 混合语言断言大小写敏感，导致 `Critical thinking` 被误判为缺失。

## 限制

- 当前只有一次最终配置下的 24 用例全量基线，尚未形成多次重复运行的置信区间。
- 评估集规模较小，尤其 Memory Update 只有 1 个用例，需要继续扩充。
- 每用例耗时包含不同数量的模型、数据库和 Graph 节点调用，不能当作单一 API 延迟或线上 SLA。
- 原始结果含模型输出，只在被 Git 忽略的本地目录留存；仓库中只提交聚合证据。

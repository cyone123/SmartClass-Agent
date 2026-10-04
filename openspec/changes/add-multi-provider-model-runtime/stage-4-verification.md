# Stage 4 verification — provider presets and compatibility matrix

Date: 2026-09-21 (Asia/Shanghai)

## Fixed integration set

| Package | Version used by the repository virtual environment |
|---|---:|
| langchain | 1.2.15 |
| langchain-core | 1.2.28 |
| langchain-openai | 1.1.11 |
| openai | 2.28.0 |

DeepSeek uses the pinned `langchain-openai` / OpenAI Chat Completions integration plus the SmartClass continuation adapter. The pinned environment does not contain `langchain-deepseek`; the compatibility adapter is selected because the pinned `ChatOpenAI` conversion drops `reasoning_content`. Offline contracts prove that non-streaming and streaming reasoning data survives internal messages, checkpoint-compatible message objects, and the next tool request.

## Offline contract gate

Command (from `backend/`):

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
.\.venv\Scripts\python.exe -m pytest -p pytest_asyncio.plugin tests/test_provider_presets.py tests/test_provider_smoke_runner.py tests/test_native_model_protocols.py tests/test_model_access.py tests/test_llm.py -q
```

Result: **102 passed**.

The contracts cover:

- OpenRouter default endpoint, explicit `openai_chat` protocol for `anthropic/*` and `deepseek/*` slugs, routing fallback, `require_parameters=true`, reasoning mapping, and actual/unknown upstream evidence.
- DeepSeek default endpoint, thinking parameter rules, `reasoning_content` non-stream/stream/tool continuation, and legacy structured-role thinking disable behavior.
- Zhipu domestic standard endpoint, custom model IDs, explicit thinking mapping, tool rules, and no model-name-driven endpoint switching.
- Safe public preset schemas for OpenAI, custom, legacy, Anthropic, Gemini, OpenRouter, DeepSeek, and Zhipu; endpoint override, multiple connections, capability source/version/verification status, and fail-closed adapter limits.
- Provider smoke report states (`passed`, `failed`, `unverified`) and the rule that missing credentials never count as passed.

## Live compatibility matrix

The live runner is separate from the 24-case evaluation YAML suite:

```powershell
.\.venv\Scripts\python.exe -m tests.provider_smoke --providers openrouter deepseek zhipu --output ..\openspec\changes\add-multi-provider-model-runtime\stage-4-provider-smoke.json
```

Optional capabilities are declared for the exact selected model with `<PREFIX>_SMOKE_CAPABILITIES=structured,thinking,vision`. The runner always checks text, stream, and a complete two-request tool roundtrip. Reports contain no endpoint, credential reference, key, prompt, completion, headers, or provider-private reasoning.

| Provider | Model | Protocol | Text | Stream | Tool roundtrip | Declared optional checks | Actual upstream |
|---|---|---|---|---|---|---|---|
| OpenRouter | unconfigured | openai_chat | unverified | unverified | unverified | none configured | unknown |
| DeepSeek | unconfigured | openai_chat | unverified | unverified | unverified | structured + thinking: unverified | unknown |
| Zhipu domestic standard API | unconfigured | openai_chat | unverified | unverified | unverified | structured + thinking: unverified | unknown |

Current report summary: **0 passed, 0 failed, 13 unverified** (`credential_or_model_missing`). The stage 4 live gate therefore remains open. Per the change specification, offline fixture success or a result from another route cannot replace each provider's own live result.

## Gate completion criteria

Task 4.6 can be checked only after all three provider/model selections have explicit credentials, all mandatory checks pass, every capability declared for that exact model passes, and the generated compatibility matrix records the model and dependency versions. OpenRouter actual upstream remains `unknown` unless the response supplies routing metadata; it is never inferred from the model slug.

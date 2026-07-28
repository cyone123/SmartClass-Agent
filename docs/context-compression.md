# SmartClass Context Compression

SmartClass context compression is a thread-level short-term context governance feature. It compresses only the LangGraph `messages` history after a completed chat turn, while keeping structured graph state such as `teaching_metadata`, `rag_context`, artifact state, and revision state authoritative and unchanged.

## Configuration

```env
CONTEXT_COMPRESSION_ENABLED=false
CONTEXT_COMPRESSION_MODEL=
CONTEXT_COMPRESSION_API_KEY=
CONTEXT_COMPRESSION_BASE_URL=
CONTEXT_COMPRESSION_TIMEOUT_MS=30000
CONTEXT_COMPRESSION_TRIGGER_TOKENS=24000
CONTEXT_COMPRESSION_KEEP_RECENT_TURNS=6
CONTEXT_COMPRESSION_MAX_OUTPUT_TOKENS=3000
CONTEXT_COMPRESSION_MAX_PREFACE_CHARS=6000
```

Recommended rollout:

- Keep `CONTEXT_COMPRESSION_ENABLED=false` for rollback and production dark launch.
- Enable locally or in a canary environment with `CONTEXT_COMPRESSION_TRIGGER_TOKENS` below the main model's context window, for example 60-75% of the effective prompt budget.
- Keep `CONTEXT_COMPRESSION_KEEP_RECENT_TURNS` at 4-8 turns so the current interaction remains raw and easy for the next model call to use.
- Set `CONTEXT_COMPRESSION_MAX_OUTPUT_TOKENS` to a bounded summary size, usually 1500-3000 tokens for teaching-design sessions.

Rollback is configuration-only: set `CONTEXT_COMPRESSION_ENABLED=false`. No database migration or message restoration job is required, and future turns will use the existing stored messages as-is.

## Model Fallback

`CONTEXT_COMPRESSION_*` settings take precedence. If the explicit compression model, API key, or base URL is absent, the backend falls back through the existing model families in this order:

1. memory model settings
2. structured-fast model settings
3. structured model settings
4. small model settings
5. main model settings

This keeps the compression boundary explicit while allowing deployments to enable the feature before provisioning a separate compressor endpoint.

## Runtime Behavior

After graph streaming completes, the backend checks estimated message tokens. If the threshold is reached, it emits a `progress` SSE event with step key `context_compression`, calls the compression model, and updates LangGraph state with one marked compressed `SystemMessage` followed by recent raw turns.

Compression is skipped when:

- the feature is disabled
- estimated tokens are below threshold
- the thread has too few older turns to compress safely
- any message required for deletion lacks an id
- a pending approval exists
- the state snapshot has a resumable interrupt

Compression failures fail open: the original messages are preserved, the stream still emits later `suggestions`, `error`, or `done` events according to the existing chat flow, and a failed progress step is sent only if compression had started.

## Frontend Expectations

No new SSE event type is introduced. The existing progress card renders the step:

```json
{
  "step_key": "context_compression",
  "label": "上下文压缩",
  "status": "running",
  "detail": "正在整理长对话上下文"
}
```

Compressed context messages are control messages for future model context. The chat UI filters messages marked with `isContextCompressed` or content beginning with `[SmartClass compressed thread context]`, both during history load and normal message rendering.

Manual verification:

- Send or load a progress payload containing `context_compression`; the existing progress card should show `上下文压缩` without parser changes.
- Load a history item whose content starts with `[SmartClass compressed thread context]`; it should not render as a chat bubble.
- Confirm normal `token`, `approval`, `suggestions`, `artifact`, `error`, and `done` events still render as before.

## Observability

Context compression emits sanitized observations:

- `context.compression.checked`
- `context.compression.skipped`
- `context.compression.started`
- `context.compression.completed`
- `context.compression.failed`

Allowed fields are bounded counters, sizes, durations, decisions, skip reasons, and error categories, such as estimated tokens, threshold, message counts, retained turn count, summary size, duration, decision, reason, `error_category`, and `error_type`.

Do not log raw message text, compressed summary text, RAG chunks, attachment bodies, memory content, JWTs, object keys, URLs, filenames, or host paths. Exporters use the existing observability sanitizer and Prometheus labels remain low-cardinality.

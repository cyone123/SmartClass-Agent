## Context

SmartClass currently stores the main conversation history in LangGraph `TeachingAssistantState.messages` using the `add_messages` reducer. The graph state also carries structured fields such as `teaching_metadata`, `rag_context`, `teaching_design_plan`, artifact results, and revision state. Several graph nodes already slice recent messages manually, but there is no thread-level compression contract, so long sessions can still accumulate large checkpoints and large LLM inputs.

The project already has separate user-level long-term memory, plan-scoped RAG, progress SSE events, OpenTelemetry/Prometheus-compatible observations, and an evaluation harness. Context compression should therefore be a governed short-term conversation mechanism, not a replacement for long-term memory or RAG.

## Goals / Non-Goals

**Goals:**

- Compress only the main `messages` conversation history for a LangGraph thread.
- Preserve graph state fields as authoritative state and use selected state fields only as structured context embedded at the beginning of the compressed context message.
- Use a dedicated configurable context compression model rather than reusing the streaming main model by default.
- Trigger compression after a completed user/AI turn when estimated context usage crosses a configurable threshold.
- Reuse the existing SSE `progress` event and progress card contract to show context compression progress.
- Fail open: compression failures must not prevent the current chat stream from completing.
- Add observability and evaluation coverage so compression behavior is measurable and regressions are caught.

**Non-Goals:**

- Do not compress or mutate `teaching_metadata`, `rag_context`, artifact state, revision state, or long-term memory records.
- Do not add a new frontend SSE event type.
- Do not archive full chat history into RAG in this change.
- Do not expose compressed context text to the frontend.
- Do not remove user-controlled approval and interrupt checkpoints.

## Decisions

### Compression Runs As A Post-Turn Runtime Step

Compression will run in the chat stream lifecycle after graph streaming completes and before the SSE `done` event. It is not a normal graph node because it is operational context governance rather than user-facing reasoning. This placement allows the backend to emit `progress` events for the existing card UI, to inspect whether the thread has pending approval, and to keep the current response intact before mutating future context.

Alternative considered: add `context_budget_node` at the beginning of the graph. That would reduce prompt size before routing, but it cannot naturally show a post-turn progress card and is riskier around `Command(resume=...)` interrupts.

### Only `messages` Are Compressed

The compressor will only delete and replace old entries in `TeachingAssistantState.messages`. Structured fields remain unchanged in state. The compressed system message will begin with a structured context preface derived from current state fields:

- teaching metadata
- teaching design plan
- RAG context digest
- artifact catalog and artifact result digest
- revision target/result digest
- pending decisions or unresolved questions if recoverable from messages

This keeps graph state authoritative while still giving future LLM calls enough context when old raw messages are removed.

Alternative considered: compress the whole graph state into a single summary. That is simpler to inject, but it weakens type boundaries and can corrupt facts that are already represented as structured state.

### Dedicated Compression Model Configuration

The backend will expose a separate compression model factory and environment variables such as `CONTEXT_COMPRESSION_MODEL`, `CONTEXT_COMPRESSION_API_KEY`, `CONTEXT_COMPRESSION_BASE_URL`, timeout, output limit, trigger threshold, recent-turn retention, and enable flag. If explicit compression model values are omitted, the implementation may fall back to the memory or structured-fast model family, but the configuration boundary remains explicit.

Alternative considered: reuse `memory_llm`. That reduces config surface, but conflates durable memory reflection with transient thread compression and makes cost/latency tuning harder.

### Threshold-Based Post-Turn Trigger

At the end of every completed user/AI turn, the runtime will estimate token usage for the thread's effective short-term context. If the estimate is below the soft threshold, it emits no progress event and continues. If it reaches the threshold, it emits `context_compression` progress as running, invokes the compression model, updates the thread state, and then emits success or failed.

The estimate should prefer provider/model token counting when available and fall back to a deterministic character-based estimate. The threshold uses configuration so deployments can tune for different model context windows.

### Pending Approval Safety

If `get_pending_approval(thread_id)` returns a pending approval or the state snapshot has a resumable interrupt, destructive message compression will be skipped. This avoids deleting messages that LangGraph may need to resume approval, clarification, or human-in-the-loop flows safely.

### Message Replacement Shape

The compressed history should be represented by one marked `SystemMessage` near the beginning of `messages`, followed by the most recent raw conversation turns. The message content should include:

1. A clear header that this is SmartClass compressed thread context.
2. A structured-state preface derived from graph state.
3. A concise summary of older user/AI conversation.
4. Explicit preserved decisions, constraints, unresolved questions, and artifact/RAG references.

When recompressing, the previous compression message is treated as input and replaced by a fresh compression message. Old messages outside the retention window are removed with LangGraph-compatible message deletion semantics instead of mutating the reducer list directly.

### Progress Event Compatibility

`context_compression` will be added to the existing progress step registry and emitted through the existing `progress` SSE event. The payload shape remains:

```json
{
  "run_id": "...",
  "phase": "agent_workflow",
  "steps": [
    {
      "step_key": "context_compression",
      "label": "上下文压缩",
      "status": "running",
      "detail": "正在整理长对话上下文"
    }
  ]
}
```

The frontend can render this through the existing progress card; no new event parser is required.

## Risks / Trade-offs

- [Risk] Compression loses an old detail needed for a later turn. -> Mitigation: keep recent raw turns, prefix structured graph state, evaluate long-session regressions, and make the feature configurable.
- [Risk] Compression mutates state during a pending approval. -> Mitigation: skip compression when a pending approval or resumable interrupt exists.
- [Risk] Compression model failure delays or breaks the chat stream. -> Mitigation: apply timeout, emit failed progress, log observation, and finish the stream with original state.
- [Risk] Compressed summaries leak sensitive attachment or RAG content. -> Mitigation: cap source text, instruct the compressor to summarize minimally, avoid frontend exposure, and rely on existing observability redaction.
- [Risk] Token estimation differs by model/provider. -> Mitigation: support model token counting where available and conservative character fallback thresholds.
- [Risk] Repeated compression drifts over time. -> Mitigation: include previous compressed summary plus recent raw turns as input, preserve state-derived facts, and add evaluation cases for multi-compression continuity.

## Migration Plan

1. Add configuration and compression model factory with the feature disabled or conservatively thresholded by default.
2. Add progress step support and observation event definitions.
3. Add compression service helpers and tests for token estimation, message selection, state-preface construction, and replacement shape.
4. Integrate post-turn compression into the chat stream lifecycle after graph completion and pending approval checks.
5. Add evaluation cases and run targeted backend tests/evals.
6. Enable in local development with a high threshold first, then tune thresholds based on observed token reduction, latency, and failure rates.

Rollback is configuration-based: disabling `CONTEXT_COMPRESSION_ENABLED` must restore the previous behavior without data migration.

## Open Questions

- The exact default token threshold should be chosen after confirming the deployed model context window and typical SmartClass lesson-design transcript length.
- The final fallback order for compression model credentials should be confirmed during implementation; the preferred boundary is explicit `CONTEXT_COMPRESSION_*` settings with documented fallbacks.

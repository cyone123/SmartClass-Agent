## Why

SmartClass keeps LangGraph thread history in the main `messages` state, so long teacher-agent sessions can grow past practical model context limits and increase latency, cost, and failure risk. The project already has long-term memory, RAG, structured teaching state, SSE progress cards, and observability primitives, making this the right time to add a governed thread-level context compression mechanism instead of relying on ad hoc recent-message slicing.

## What Changes

- Add a dedicated context compression capability for SmartClass agent threads.
- Use a configurable, dedicated compression model to summarize only the main conversation `messages`.
- Preserve graph state fields such as `teaching_metadata`, `rag_context`, `teaching_design_plan`, artifact catalog, and revision results as authoritative structured state rather than compressing them in place.
- Prefix the compressed context with selected structured graph state so later LLM calls can recover key teaching facts, RAG facts, artifact status, and decisions without replaying every old message.
- Trigger compression after each completed user/AI turn when the estimated token budget crosses a configurable threshold.
- Emit existing SSE `progress` events for a `context_compression` step so the frontend can show the current progress card while compression runs.
- Skip destructive compression while a thread has a pending approval or resumable interrupt.
- Add observability events and evaluation cases for compression decisions, success/failure, token reduction, and regression safety.

## Capabilities

### New Capabilities

- `context-compression`: Thread-level short-term context compression for SmartClass agent conversations, covering trigger policy, compressed message shape, state preservation, SSE progress visibility, failure handling, and evaluation.

### Modified Capabilities

- `external-observability`: Add context compression observation events and metric field constraints while preserving low-cardinality labels and sensitive-content redaction.

## Impact

- Backend graph/runtime: agent streaming lifecycle, LangGraph thread state updates, message deletion/replacement semantics, compression trigger checks, approval/interrupt safety checks.
- Backend configuration: dedicated compression model settings, enable flag, token thresholds, recent-turn retention, maximum compressed context size, timeout/failure policy.
- Backend progress/SSE: add a `context_compression` progress step using the existing `progress` SSE event contract.
- Backend observability: add compression observation events with sanitized size/count/duration fields and no raw prompt, completion, RAG chunk, attachment body, JWT, object key, or host path logging.
- Frontend chat UI: consume the new progress step through the existing progress card without introducing a new SSE event type.
- Evaluation harness: add compression regression cases for long conversations, structured teaching metadata preservation, artifact revision continuity, RAG summary handling, approval safety, and compression failure fallback.

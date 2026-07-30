## 1. Configuration And Model Setup

- [x] 1.1 Add context compression configuration getters for enable flag, model, API key, base URL, timeout, trigger token threshold, recent-turn retention, and maximum compressed output size.
- [x] 1.2 Add a dedicated context compression model factory in the backend LLM layer with documented fallback behavior when explicit `CONTEXT_COMPRESSION_*` values are absent.
- [x] 1.3 Add example environment variables to local/Docker environment examples without committing real credentials.

## 2. Compression Service

- [x] 2.1 Create a backend context compression module that identifies compressible main `messages`, prior compressed context messages, and recent raw turns to retain.
- [x] 2.2 Implement token estimation with provider/model token counting when available and a deterministic character-based fallback.
- [x] 2.3 Implement structured state preface construction from `teaching_metadata`, `rag_context`, `rag_results`, `teaching_design_plan`, artifact catalog/results, and revision state without mutating those state fields.
- [x] 2.4 Implement the compression prompt and output normalization so the result is concise, bounded, and marked as SmartClass compressed thread context.
- [x] 2.5 Implement LangGraph-compatible message replacement using deletion semantics for old messages and insertion of one marked compressed `SystemMessage` plus recent raw turns.
- [x] 2.6 Add service-level unit tests for threshold decisions, retention selection, structured preface content, repeated compression, and failure fallback.

## 3. Runtime Integration

- [x] 3.1 Add `context_compression` to backend progress step keys, ordering, and labels.
- [x] 3.2 Integrate post-turn compression into `AgentRuntime.stream_agent_events()` after graph streaming completes and before suggestions or final `done` emission.
- [x] 3.3 Ensure compression is skipped when the thread has pending approval or a resumable interrupt.
- [x] 3.4 Emit `context_compression` progress events with running, success, and failed statuses using the existing `progress` SSE contract.
- [x] 3.5 Ensure compression failures preserve original message state and do not prevent `suggestions`, `error`, or `done` events from following existing stream behavior.

## 4. Frontend Compatibility

- [x] 4.1 Verify the existing chat progress card renders the new `context_compression` step without requiring a new SSE event type.
- [x] 4.2 Hide or filter marked compressed context control messages from normal chat history rendering.
- [x] 4.3 Add or update frontend tests/manual verification notes for progress display and compressed-message filtering.

## 5. Observability

- [x] 5.1 Emit sanitized context compression observations for checked, skipped, started, completed, and failed outcomes.
- [x] 5.2 Include bounded fields such as estimated tokens, threshold, message counts, retained turn count, summary size, duration, decision, skip reason, and error category.
- [x] 5.3 Verify logs, JSONL traces, OpenTelemetry attributes, and Prometheus labels do not include raw messages, summary text, RAG chunks, attachment bodies, memory content, JWTs, object keys, URLs, filenames, or host paths.
- [x] 5.4 Add or update observability tests covering redaction and low-cardinality metric behavior for compression events.

## 6. Evaluation And Regression Coverage

- [x] 6.1 Add context compression evaluation cases for long teaching-design conversations that preserve teaching metadata after compression.
- [x] 6.2 Add evaluation or unit coverage for artifact revision routing after compression.
- [x] 6.3 Add approval/interruption safety coverage proving compression is skipped while approval is pending.
- [x] 6.4 Add compression model failure fallback coverage proving the chat stream completes and messages are not destructively changed.
- [x] 6.5 Run targeted backend tests and relevant eval categories, recording any model/API prerequisites or skipped cases.

## 7. Documentation And Rollout

- [x] 7.1 Document the context compression configuration, recommended thresholds, fallback behavior, and rollback switch.
- [x] 7.2 Document operational expectations for compression progress cards and observation events.
- [x] 7.3 Validate the change with `openspec status --change add-context-compression` and `openspec validate add-context-compression` before implementation is considered complete.

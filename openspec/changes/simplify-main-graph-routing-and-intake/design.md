## Context

See `proposal.md` for motivation and `specs/conversational-teaching-orchestration/spec.md` for the behavior contract.

The current graph uses a structured-output route followed by a second model node for normal chat. Teaching intake separately invokes structured metadata extraction, a conditional completeness function, a follow-up model, and a generic clarification interrupt. Metadata and plan approvals already use durable LangGraph interrupts, the runtime discovers pending approvals from checkpoints, and the frontend renders progress and approval cards from business payloads rather than graph topology.

`messages` is checkpointed with an additive reducer. Free-text clarification resumes through a generic interrupt that appends the user's reply, while context compression already skips threads with resumable interrupts. Profile is a bounded session snapshot loaded before routing. Experience has a separate lifecycle: eligible normal chat uses turn-scoped retrieval, while teaching planning establishes a scope-keyed snapshot shared across approval resume and artifact branches.

## Goals / Non-Goals

**Goals:**

- Make ordinary chat a one-model-call path unless it explicitly needs a bounded Experience lookup.
- Let one entry model role choose between visible response, teaching-design action, and artifact-revision action.
- Let one intake model role ask each clarification or submit final canonical metadata without persisting partial metadata per turn.
- Preserve durable resume semantics and existing frontend/SSE contracts.
- Keep memory retrieval at its correct session, turn, and approved-task boundaries.
- Reduce graph/model coupling in tests and observations while retaining safe fallbacks.

**Non-Goals:**

- Simplifying the internal artifact-revision, artifact-generation, or fan-in graphs beyond connecting them to the new entry action.
- Removing Profile initialization, approval interrupts, generation branches, or artifact fan-in solely to reduce node count.
- Changing public chat-run endpoints, SSE event names, approval request schemas, artifact types, or memory CRUD APIs.
- Using historical Profile facts to infer missing teaching requirements.
- Persisting model chain-of-thought or exposing internal tool protocol to clients.

## Decisions

### 1. Replace route-plus-response with one bounded conversation entry agent

Bind the main conversation model to two internal action schemas:

```text
start_teaching_design(initial_request)
revise_artifact(request, suggested_targets)
```

No action call means the returned text is the ordinary-chat response. A valid action is interpreted inside the entry node and converted directly to a state update plus `Command(goto=...)`; it is not executed through a general-purpose `ToolNode`. These actions have no external side effects.

The entry prompt requires exactly one outcome and gives teaching workflow actions precedence over a social preamble in mixed messages. It receives the trusted, sanitized artifact catalog needed to preserve revision routing. On each outcome it writes the compatible `intent` state used by reflection and evaluation and writes `teaching_task_initial_request` only when starting a new teaching task.

Alternative considered: keep structured intent output and merge only normal response generation. Rejected because it retains two calls for ordinary chat and the dedicated route schema.

Alternative considered: add a `ToolNode` for action dispatch. Rejected because it adds graph topology for local control-only actions and makes tool execution appear more general than it is.

### 2. Use one intake agent and materialize metadata only on final submission

The teaching-intake model reads a bounded slice of messages for the active teaching task. While incomplete it returns one visible question. The node appends that response and goes to the existing generic clarification interrupt. The next user message resumes directly into intake, avoiding another entry call.

When complete, the model calls one internal action:

```text
submit_metadata_for_review(
  subject,
  grade,
  topic,
  course_duration,
  core_points,
  key_points,
  difficult_points,
  teaching_objectives
)
```

The backend validates and bounds the arguments, creates the canonical `teaching_metadata` snapshot, and sets `is_complete=true` for compatibility. The tool-call message is protocol-only and is not appended to visible conversation history. Tool choice expresses the model's completeness judgment, while deterministic validation prevents an invalid snapshot from entering approval.

Alternative considered: persist a partial metadata object on every question. Rejected because the task conversation is already durable, the expected clarification depth is small, and partial merging creates additional state and correction semantics.

Alternative considered: let incomplete intake return only unstructured text with no task boundary. Rejected because an unbounded thread can contain older teaching tasks and unrelated context.

### 3. Preserve an explicit teaching-task boundary without partial metadata

Keep `teaching_task_initial_request` and add a stable active-task boundary, such as a generated task-scope identifier plus a start message identifier/index that survives checkpoints. Intake context selection includes:

```text
initial request for the active teaching task
+ intake questions for that task
+ user clarifications and corrections for that task
+ previous submitted metadata only when revising an approval
```

It excludes earlier tasks, approval acknowledgements, artifact-generation tool traffic, RAG chunks, memory bodies, and full repeated attachment bodies. Start, cancel, replacement, completion, and artifact-revision transitions explicitly open or close the active intake scope.

If the bounded task transcript approaches its budget, reuse the established context-compression primitives or introduce a task-scoped intake summary that preserves explicit facts and corrections. Do not compress destructively while a resumable interrupt is pending.

### 4. Keep generic clarification and approval interrupts as separate replay boundaries

The intake node must complete and checkpoint its question before entering the generic clarification interrupt. Metadata submission must complete and checkpoint before entering the metadata-review interrupt. No model call or non-idempotent work occurs before `interrupt()` in an interrupt node.

This separation is intentional: LangGraph re-executes an interrupted node on resume. Calling the model and then interrupting in the same node could repeat model work and change the reviewed payload.

The metadata-review node retains the `metadata_review` payload and routes approval to context preparation. Rejection appends the user's correction and returns to intake. Teaching-plan review remains unchanged.

### 5. Treat model tools as validated protocol, not arbitrary capabilities

Action schemas are allowlisted per model stage. Dispatch rejects unknown tools, multiple business actions, invalid target values, excessive arguments, and a response containing both actionable text and a business action. The runtime performs at most one bounded repair attempt, then uses the configured reliable fallback or returns a safe visible error/clarification.

Tool calling remains structured provider interaction even though the dedicated `with_structured_output` route and metadata pipelines are removed. Models and provider settings must support the chosen tool protocol, including the existing DeepSeek-compatible thinking behavior. Fallback observes the same bounded Profile/task context and does not repeat memory retrieval.

### 6. Preserve streaming by committing only user-visible message content

Add the entry and intake nodes to the root streaming allowlist. Ordinary response tokens stream directly. Intake questions are returned as visible `AIMessage` content and therefore stream or arrive as a complete message through the same `token` event path.

Internal action arguments are never converted to text events or history messages. Prompts prohibit textual preambles beside actions. The dispatcher also suppresses empty placeholders and rejects conflicting content/action results. The existing post-run checkpoint inspection remains the only source of `approval` events, ensuring an action alone cannot display an approval card before the durable interrupt exists.

Keep the current event names. Continue using stable progress keys such as `intent_recognition`, `metadata_structuring`, `metadata_review`, `rag_retrieval`, and `teaching_design` during migration; user-facing labels may describe the consolidated work more accurately without changing keys.

### 7. Preserve memory boundaries and use an optional bounded memory round for ordinary chat

Profile initialization remains the graph bootstrap and the same bounded snapshot is injected into entry and intake. The intake system prompt states that Profile is untrusted historical background and cannot fill missing current-task facts.

Experience is not automatically resolved during teaching intake. After metadata approval, a context-preparation boundary builds the final bounded teaching-task query and resolves/reuses the scope-keyed Experience snapshot. RAG and Experience resolution are independent after approval, so the implementation obtains them concurrently when both are enabled, records their outcomes separately, and supplies both to the planner. Existing artifact branches reuse the checkpointed snapshot.

For ordinary teaching-related discussion, the entry agent may invoke one allowlisted, bounded, read-only Experience search and then answer in a second round within the same graph node/model role. This preserves turn-scoped relevance without prefetching and discarding Experience on every teaching-design action. The result is not promoted into teaching-task state.

Alternative considered: prefetch Experience using keyword rules before the entry call. Rejected because it duplicates retrieval for teaching-design requests and reintroduces a heuristic business classifier.

Alternative considered: remove Experience from ordinary chat. Rejected because it regresses the established memory behavior.

### 8. Keep business observations independent of node topology

Progress continues to use stable business-stage keys. Add sanitized action outcome, validation outcome, repair/fallback outcome, task-scope transition, and model-call-count fields to observations where useful. Do not log prompts, tool arguments, metadata bodies, memory queries/bodies, attachments, artifact catalog content, object identifiers, URLs, or host paths.

Evaluation adapters assert the entry outcome, final graph state, visible response, pending interrupt, and event sequence rather than importing removed node functions. Efficiency evidence reports calls and latency by scenario; memory-assisted ordinary chat is reported separately because it can legitimately require a second model round.

### 9. Migrate in-flight checkpoints safely

Keep the names and semantics of the generic clarification, metadata-review, and teaching-plan-review interrupt nodes. Their persisted checkpoints can therefore resume against the new outgoing routes.

During one compatibility window, register thin legacy aliases for any removed node name that may exist as a checkpoint's pending `next` value. Each alias deterministically forwards to the new entry or intake node without invoking the legacy model logic. After confirming no resumable checkpoints reference the aliases, remove them in a later cleanup rather than silently invalidating active threads.

## Risks / Trade-offs

- [The intake model repeatedly rereads task messages instead of a compact partial object] -> Bound context to the active task, cap clarification depth, exclude repeated attachment bodies, and add task-scoped summarization only when measured limits require it.
- [A tool-capable model emits text and an action together] -> Require exclusivity in the prompt, validate after invocation, suppress protocol leakage, and perform a single bounded repair/fallback.
- [Tool streaming produces partial internal arguments] -> Emit only text content from allowlisted root nodes and derive approval solely from a persisted interrupt payload.
- [Old task messages contaminate a new intake] -> Persist and test an explicit active-task boundary and reset it on start/cancel/replacement/completion transitions.
- [Profile memory hallucinates current teaching facts] -> Label Profile as untrusted history and test that absent subject/grade/topic remain missing despite historical values.
- [Ordinary-chat memory search increases latency] -> Limit it to one explicit read-only action, report memory-assisted latency separately, and let simple chat answer in one call.
- [Concurrent RAG and Experience failure handling becomes coupled] -> Preserve separate result/degradation fields and fail open independently according to the existing policies.
- [Deploying after removing nodes strands old checkpoints] -> Retain forwarding aliases for a measured compatibility period and inspect aggregate pending-node counts without exposing thread identifiers.

## Migration Plan

1. Add action schemas, task-boundary state, validators, safe observations, and compatibility tests without changing graph routing.
2. Add the conversation entry agent behind a configuration flag and verify ordinary, teaching, revision, mixed-intent, fallback, and token-stream paths.
3. Add the teaching-intake agent, route incomplete responses through the existing generic interrupt, and keep legacy nodes as forwarding aliases.
4. Route final validated metadata through the unchanged metadata-review payload and verify rejection/correction and stale-approval behavior.
5. Move teaching-task Experience resolution into post-approval context preparation and run RAG and Experience concurrently while preserving checkpoint snapshot reuse.
6. Update SSE/frontend contract tests, evaluation adapters, progress/observation tests, and model-call/latency evidence.
7. Enable the simplified graph by default after regression gates pass; retain a short rollback flag and legacy checkpoint aliases.
8. Roll back by restoring the legacy routing flag. Existing final metadata, approvals, artifacts, and memory snapshots remain compatible. Remove aliases only in a separately verified cleanup.

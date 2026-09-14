## Context

See `proposal.md` for motivation and `specs/long-term-memory-retrieval/spec.md` for the behavior contract.

The first implementation established a session-level Profile snapshot, removed fixed Experience retrieval nodes, introduced `MemoryRequest`/`MemoryContextProvider`/`ModelRuntime`, and added artifact-agent memory middleware. Subsequent review exposed four gaps:

1. Ordinary chat queries use the latest user message, while teaching and artifact queries add metadata/plan fields but can still lose the initial teaching intent after multi-turn clarification.
2. `AsyncPostgresStore` is constructed without an index configuration and memory writes use `index=False`; in the installed LangGraph version a query can therefore be silently ignored and results fall back to recency order.
3. Teaching design and each artifact branch own separate request caches, so one teaching flow can repeat substantially similar Experience retrieval up to four times.
4. Artifact middleware resolves lazily at every model-call boundary. Its cache avoids repeated Store access, but every tool round still performs request lookup, fingerprint/cache work, and context composition.

The Agent runnables are created once and reused across tasks, while each artifact invocation already has a distinct runtime configuration and one initial prompt. LangChain supports a per-invocation runtime `context` and an official `@dynamic_prompt` middleware. This permits one task-specific prompt to be rendered before Agent execution without rebuilding the Agent graph.

## Goals / Non-Goals

**Goals:**

- Keep Profile as a simple bounded session snapshot loaded once.
- Improve Experience recall for multi-turn tasks through a stable bounded task summary and actual semantic candidate search.
- Resolve and checkpoint one bounded Experience snapshot per teaching-task scope, then share it across planning, approval/resume, and artifact fan-out.
- Remove automatic Experience retrieval and cache machinery from artifact model-call middleware.
- Render each artifact task's complete system prompt once and reuse the same immutable prompt across tool rounds through runtime context.
- Preserve exact-title optimization, selector fallback for ambiguity, explicit on-demand Agent search, privacy, fail-open behavior, and safe observations.

**Non-Goals:**

- Changing Profile/Experience public APIs, namespaces, content schema, or mutation semantics.
- Changing the reflection worker, its single-worker/at-most-once behavior, or mutation guards.
- Introducing cross-session caches or distributed cache invalidation.
- Semantically indexing Profile memory or raw full conversation/attachment content.
- Automatically refreshing an unchanged workflow snapshot whenever background Experience writes commit.
- Removing the explicit read-only `search_experience_memory` Agent tool.

## Decisions

### 1. Keep Profile initialization unchanged

`profile_memory_load_node` remains the graph bootstrap. It reads the authenticated Profile namespace, renders the bounded set deterministically, and stores the resulting session snapshot in graph state:

```text
profile_memory_loaded
profile_memory_context
profile_memory_item_count
profile_memory_truncated
```

All applicable calls reuse this value. There is no Profile selector, semantic search, purpose filtering, request fingerprint, or separate cache.

### 2. Build a bounded teaching-task query rather than using the latest message alone

Introduce one deterministic query builder that receives only explicitly selected fields. For a teaching workflow it composes:

```text
initial teaching request
+ last 2-3 relevant user clarifications
+ confirmed subject / grade / topic
+ objectives / key points / difficult points
+ current task kind
+ revision scope when applicable
```

The builder excludes approval acknowledgements, tool messages, assistant output, attachment bodies, RAG chunks, authorization material, and checkpoint internals. Each component and the final string are bounded. Structured metadata remains authoritative when it duplicates free text.

The initial request is the first substantive HumanMessage associated with the current teaching task, not necessarily the first message in the entire thread. Scope selection must therefore respect the active plan/task boundary where available. Normal chat may use a smaller turn query because it is intentionally not promoted into a teaching snapshot.

Alternative considered: pass the complete conversation to embeddings or the selector. Rejected because it increases noise, privacy exposure, token use, and sensitivity to unrelated prior turns.

### 3. Enable semantic indexing only for Experience

Construct `AsyncPostgresStore` with a configured LangChain-compatible embedding model, embedding dimensions, and indexed paths. Reuse the existing embeddings configuration/model factory rather than hard-coding a provider. Index only bounded descriptive Experience fields such as:

```text
title
summary
tags
```

Profile writes continue with `index=False`. Experience writes enable indexing explicitly. Startup configuration validation must reject internally inconsistent settings such as semantic retrieval enabled without an embedding model/dimension configuration. A Store capability check and real-Postgres test must ensure query results include semantic scores; recency fallback must never be reported as successful semantic retrieval.

Existing Experience rows need an idempotent administrative backfill that rereads each authenticated namespace/item and reissues an indexed write without changing the item key, ownership, timestamps exposed by the API, or memory content. The migration must be restartable and report only aggregate counts/errors.

Alternative considered: continue loading up to 100 recent summaries and let the selector choose. Rejected because the summary character budget means the selector usually sees only a small recent prefix and cannot recover older relevant memories.

### 4. Use semantic candidates before selector reranking

Provider resolution becomes:

```text
MemoryRequest
    |
    v
bounded teaching-task query
    |
    +--> deterministic exact-title match
    |
    v
semantic top-K over Experience descriptive fields
    |
    +--> sufficient confidence/order: select directly
    |
    +--> ambiguous: selector reranks bounded summaries
    |
    v
load selected content --> deduplicate --> item/char budgets
    |
    v
MemoryBundle / ExperienceSnapshot
```

Semantic query results preserve Store relevance order and score metadata. Generic memory list APIs can retain their existing deterministic/recency order, but the semantic retrieval path must not sort candidates again by `updated_at`. Exact-title detection remains independent of vector score. Selector output remains constrained to IDs from the presented candidate set.

A small recency supplement may be merged with semantic top-K only if tests show it improves newly written-memory recall; semantic ordering remains primary and duplicates are removed. Score thresholds and selector-bypass thresholds are configuration values with conservative defaults, not hard-coded provider assumptions.

### 5. Promote resolved Experience to a bounded task snapshot

Experience lifecycle changes from model-call scope to teaching-task scope. Add durable graph-state fields equivalent to:

```text
experience_memory_scope_key: str
experience_memory_context: str
experience_memory_selected_ids: list[str]
experience_memory_strategy: str
experience_memory_truncated: bool
experience_memory_degraded: bool
```

The scope key is a deterministic digest of the normalized task query and retrieval-affecting limits/version, never raw user text. Selected IDs and bodies remain state data and are not emitted to logs or metrics. The context is already character-bounded by the provider.

Teaching design is the first consumer after metadata confirmation. At that boundary it computes the scope key, reuses a matching snapshot or resolves once, passes the bundle to the planner, and returns the snapshot fields with the node result. Approval/checkpoint then preserves it for artifact fan-out and resume.

All artifact branches consume the same snapshot. Artifact type alone does not trigger automatic retrieval because the reusable teaching Experience is expected to overlap. If an Agent needs specialized information, it can explicitly call the bounded search tool.

Revision behavior is explicit:

- Same plan/task and a presentation-only change reuses the snapshot.
- A change to teaching topic, audience, objectives, key/difficult points, or other retrieval-significant metadata creates one new scope and resolves once before revision fan-out.
- Every branch in that revision scope shares the refreshed snapshot.

This intentionally supersedes the earlier decision that Experience bodies must remain call-local. A bounded snapshot in the existing protected checkpoint is the simplest way to reuse context across approval interrupts and parallel nodes. It does not change the memory's long-term storage status or make it observable.

Alternative considered: persist only selected IDs and reload bodies in each branch. Rejected because it adds Store calls and failure modes while providing little additional protection over other bounded user-derived checkpoint state.

### 6. Let `ModelRuntime` consume either a request or a resolved bundle

`ModelRuntime` remains the common boundary for ordinary, structured/fallback, and streaming calls. Its APIs accept mutually exclusive inputs:

```text
memory_request=None        # runtime resolves when a turn-local call needs Experience
memory_bundle=None         # orchestration supplies an existing task snapshot
```

Teaching design supplies the resolved bundle after `ensure_experience_snapshot`. Eligible normal chat can continue supplying a turn-scoped request. Structured primary/fallback calls reuse the exact same resolved bundle. Internal memory calls continue using memory-disabled context to prevent recursion.

Request fingerprint/single-flight caching is no longer part of the artifact integration. A small transient cache may remain inside `ModelContext` only for one ordinary structured/fallback operation, where it has a concrete reuse purpose; it must not define workflow sharing semantics.

### 7. Pre-render the artifact system prompt once per task

Define a complete artifact system-message template with explicit fields for:

```text
base artifact-agent instructions and execution contract
artifact-specific instructions
bounded Profile background
bounded shared Experience background
```

At `_run_artifact_job`, render the complete prompt once from trusted state and pass it through LangGraph/LangChain's per-invocation `context=` argument. The reusable Agent is created with an artifact context schema and a lightweight official `@dynamic_prompt` hook:

```text
artifact task start
    |
    +--> render complete system prompt once
    |
    +--> agent.astream(..., context={system_prompt: rendered_prompt})
                              |
                              +--> each model round returns same immutable prompt
```

The hook executes for every stateless model request because the system prompt must be sent on every API call, but it performs only a runtime-context lookup. It does not build a `MemoryRequest`, access Store, invoke a selector, calculate a fingerprint, inspect a memory cache, or concatenate memory sections.

The template labels Profile and Experience as untrusted historical background and states that current explicit user instructions and system/developer rules take precedence. The whole rendered prompt remains bounded and task-local. Each parallel branch gets its own rendered prompt with its artifact instructions and the same shared snapshots.

Alternative considered: append memory to the initial HumanMessage. It would persist through the tool loop and is simpler, but system context gives clearer trust/priority semantics and avoids treating historical background as a current user instruction.

Alternative considered: call `create_agent` per artifact task with a formatted static `system_prompt`. Rejected because it rebuilds a reusable compiled graph for every job and is unnecessary when runtime context is supported.

### 8. Keep explicit Agent search separate from automatic context

`search_experience_memory(query)` remains available to eligible artifact Agents under the existing skill execution policy. It binds user identity from trusted runtime context, applies a lower result budget, and invokes the same semantic provider for a new query. It must not return or mutate the shared snapshot, and repeated calls are observable as explicit tool searches rather than hidden automatic retrieval.

### 9. Preserve fail-open behavior and safe observability

Missing/unavailable semantic search, Store failures, embedding failures, and selector failures yield an empty degraded bundle for non-required requests. Model and artifact execution continues. Misconfiguration is still surfaced at startup/health verification so fail-open does not become silent false confidence.

Record only low-cardinality fields: purpose, strategy, semantic/selector/degraded outcome, candidate/selected count, truncation, snapshot reused/refreshed, and duration. Never record query text, prompt text, memory bodies, selected IDs, user/run/thread IDs as metric labels, attachment content, URLs, keys, or host paths.

## Risks / Trade-offs

- [Embedding configuration or dimensions do not match the Store index] -> Validate configuration before Store setup and cover the real Postgres path with an integration test that asserts non-null scores and relevance ordering.
- [Backfill is expensive on a large deployment] -> Make it idempotent, bounded/batched, restartable, and separately invokable; do not block normal startup on a full backfill.
- [A task snapshot becomes stale after new Experience is written] -> Treat this as intentional task consistency and refresh only at a documented new-scope boundary.
- [Persisted Experience context increases checkpoint size] -> Enforce the existing strict item/character budget and store only the rendered bounded snapshot plus small metadata.
- [Scope-key mistakes reuse irrelevant memory] -> Derive the key from normalized retrieval-significant fields and test unchanged artifact-only revisions versus changed teaching scope.
- [Semantic thresholds vary by embedding model] -> Keep thresholds configurable and evaluate with real embeddings; fall back to bounded selector reranking when confidence is ambiguous.
- [Dynamic prompt replaces rather than appends the static prompt] -> Pre-render the complete prompt, including all base and artifact-specific instructions, and test exact presence once per model request.
- [Explicit Agent search reintroduces repeated retrieval] -> Keep it skill-authorized, clearly described as supplemental, tightly bounded, and observable; do not call it automatically.

## Migration Plan

1. Add semantic-search configuration validation and initialize the Postgres Store index using the existing embeddings role.
2. Split generic recency listing from semantic Experience search, enable indexing on new Experience writes, and add an idempotent backfill command/path for existing rows.
3. Revise the provider to pass the task query into semantic search, preserve score ordering, and use selector reranking only for ambiguity.
4. Add the bounded task-query builder, scope key, and Experience snapshot state; update teaching design and revision boundaries to resolve/reuse one snapshot.
5. Extend `ModelRuntime` to accept pre-resolved bundles while preserving turn-local request and structured fallback behavior.
6. Replace artifact memory retrieval middleware/cache configuration with a typed runtime context, one-time system-prompt render, and lightweight `@dynamic_prompt` hook.
7. Update observations, unit/integration/evaluation tests, environment templates, and documentation; run strict OpenSpec validation and backend regression gates.
8. Run the idempotent Experience index backfill in deployment before relying on semantic recall for historical rows.

Rollback can disable semantic retrieval, restore recency/selector candidate loading, remove snapshot reuse, and restore the previous artifact middleware without rewriting Profile or Experience content. Indexed vectors may remain unused after rollback.

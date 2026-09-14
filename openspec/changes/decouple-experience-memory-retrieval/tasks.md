## 1. Existing Retrieval Contracts and Profile Baseline

- [x] 1.1 Add immutable Experience-only `MemoryRequest`, bounded `MemoryQuery`, and structured `MemoryBundle` contracts, and verify validation rejects caller-supplied identity, invalid purposes, and invalid budgets.
- [x] 1.2 Extract Experience selection, content loading, rendering, and budget enforcement behind `MemoryContextProvider`, and verify exact-title, selector validation, truncation, empty, and fail-open cases.
- [x] 1.3 Preserve account-scoped namespaces and sanitized selector inputs, and verify tests prevent cross-user access and sensitive query material.
- [x] 1.4 Add explicit Profile initialization state, deterministic bounded loading, interrupt/resume reuse, and background-data delimiters, and verify populated, empty, truncated, failure, and precedence tests.

## 2. Existing Runtime and Graph Baseline

- [x] 2.1 Introduce `ModelContext` and `ModelRuntime` around existing model roles without moving graph, checkpoint, SSE, workspace, or mutation responsibilities, and verify ordinary/structured/streaming behavior.
- [x] 2.2 Migrate applicable main-graph calls to `ModelRuntime`, remove the four fixed Experience retrieval nodes, and verify graph topology routes directly to business nodes.
- [x] 2.3 Preserve internal-memory mode, structured primary/fallback bundle reuse, and pre-stream retrieval, and verify recursion, fallback, and streaming tests.
- [x] 2.4 Add the bounded read-only `search_experience_memory` Agent tool with trusted identity and existing skill-policy authorization, and verify identity, write, size, and authorization guards.

## 3. Teaching-Task Query Construction

- [x] 3.1 Implement a deterministic bounded teaching-task query builder using the task's initial substantive request, the last 2-3 relevant user clarifications, confirmed metadata, and revision scope, and verify multi-turn tests retain the original intent when the latest message is only a partial clarification.
- [x] 3.2 Exclude approval acknowledgements, assistant/tool messages, attachments, RAG bodies, checkpoint internals, and sensitive runtime material from task queries, and verify focused privacy/budget tests.
- [x] 3.3 Use the shared query builder for teaching design, scope refresh, and eligible normal-chat variants without passing the whole graph state, and verify stable normalization produces the same query/scope for equivalent input.

## 4. LangGraph Store Semantic Search

- [x] 4.1 Add configuration for enabling Experience semantic retrieval, embedding dimensions, indexed fields, candidate limits, and optional confidence thresholds using the existing embeddings role; update local/Docker environment templates and verify default/invalid configuration tests.
- [x] 4.2 Construct `AsyncPostgresStore` with a compatible index configuration and add startup/capability validation that detects missing or incompatible semantic configuration instead of silently reporting recency retrieval as semantic.
- [x] 4.3 Keep Profile writes explicitly unindexed while enabling semantic indexing for new/updated Experience writes over bounded `title`, `summary`, and `tags` fields, and verify write-path tests distinguish both memory kinds.
- [x] 4.4 Add an idempotent, batched Experience index-backfill path for existing rows that preserves keys, ownership, and public content and emits only safe aggregate progress; verify rerunning it does not duplicate or mutate memories.
- [x] 4.5 Split generic recency listing from semantic Experience search, pass the bounded query to Store search, retain relevance order/score metadata, and verify no `updated_at` resort destroys semantic ranking.
- [x] 4.6 Add a real Postgres/pgvector integration test asserting semantic scores are present and a relevant Experience ranks above an unrelated one; also verify the unavailable-index path is explicitly degraded rather than mislabeled.

## 5. Provider Selection Pipeline

- [x] 5.1 Revise `MemoryContextProvider` to combine exact-title matching with semantic top-K candidates and bounded content loading, and verify older relevant memories can beat newer unrelated memories.
- [x] 5.2 Add configurable confidence handling so high-confidence semantic results can bypass the selector while ambiguous candidates use bounded selector reranking, and verify both paths, invalid selector IDs, deduplication, and item/character limits.
- [x] 5.3 Preserve fail-open behavior for Store, embedding, and selector failures while distinguishing exact, semantic, selector, empty, and degraded strategies in safe result metadata and tests.
- [x] 5.4 Remove provider/caller assumptions that candidate count alone implies selector visibility, and verify the exact summaries passed to the selector respect their own bounded candidate and character budgets.

## 6. Shared Experience Snapshot

- [x] 6.1 Extend graph state with bounded Experience snapshot context, selected IDs, scope key, strategy, truncation, and degradation fields, and verify checkpoint serialization contains no request object, cache, Store handle, or unbounded content.
- [x] 6.2 Implement deterministic scope-key generation from normalized retrieval-significant task fields and effective limits/version, and verify raw queries and user identity are not exposed in the key or observations.
- [x] 6.3 Resolve or reuse the snapshot at the teaching-design consumption boundary after metadata confirmation, pass the resolved bundle to the planner, and verify one provider call covers planning through approval resume.
- [x] 6.4 Reuse the same snapshot across PPT, DOCX, and HTML generation fan-out without automatic per-artifact retrieval, and verify a complete three-artifact flow performs one teaching-task Experience resolution.
- [x] 6.5 Implement revision refresh rules: reuse for artifact-only changes, refresh once for retrieval-significant topic/audience/objective/metadata changes, and share the refreshed snapshot across revision branches; verify both boundaries.
- [x] 6.6 Keep eligible normal-chat Experience retrieval turn-scoped and verify it neither overwrites nor implicitly reuses an unrelated teaching-task snapshot.

## 7. ModelRuntime Bundle Consumption

- [x] 7.1 Extend `ModelRuntime` invocation paths to accept either a turn-local `MemoryRequest` or an already resolved `MemoryBundle`, reject ambiguous simultaneous inputs, and verify ordinary, structured/fallback, and streaming calls compose exactly one bounded memory section.
- [x] 7.2 Update teaching-design and shared-workflow callers to supply the resolved snapshot while retaining request resolution only where turn-local retrieval is intended, and verify no provider call occurs when a bundle is supplied.
- [x] 7.3 Remove workflow-sharing dependence on request fingerprints/single-flight caches while retaining only the minimal fallback/turn-local reuse needed inside one invocation, and verify concurrent artifact branches require no shared mutable cache.

## 8. Artifact Dynamic System Prompt

- [x] 8.1 Define a typed artifact runtime context and a complete bounded system-message template containing base contract, artifact-specific instructions, session Profile, shared Experience, delimiters, and current-instruction precedence; verify escaping and exactly-once section composition.
- [x] 8.2 Render the complete artifact system prompt once at each generation/revision task start and pass it through `agent.astream(..., context=...)`, and verify parallel branches receive isolated task prompts with the same shared memory snapshot.
- [x] 8.3 Replace `MemoryContextMiddleware` with LangChain's lightweight `@dynamic_prompt` integration that only returns the pre-rendered prompt on each model round, and verify multi-tool-round tests perform no Store query, selector call, fingerprinting, cache lookup, or repeated prompt construction.
- [x] 8.4 Remove artifact `experience_memory_request` and `experience_memory_cache` configuration plumbing and obsolete automatic retrieval tests while preserving LLM observation and all other middleware ordering/behavior.
- [x] 8.5 Keep explicit `search_experience_memory` supplemental and read-only, route it through semantic provider behavior for genuinely new queries, and verify it cannot mutate the shared snapshot or bypass skill authorization.

## 9. Observability and Evaluation

- [x] 9.1 Update observations for semantic strategy/degradation and snapshot reuse/refresh while excluding queries, prompts, bodies, selected IDs, users/runs/threads, paths, keys, and URLs from logs and metric labels; verify safe-observability tests.
- [x] 9.2 Update unit and evaluation cases for multi-turn query retention, older semantic matches, high-confidence bypass, ambiguous reranking, one-resolution teaching fan-out, approval resume, revision refresh, and dynamic system-prompt reuse.
- [x] 9.3 Verify `python -m tests.evals.cli validate-suite --expected-count 24` succeeds, or intentionally update the documented expected count and suite metadata when cases are added.

## 10. Regression Verification

- [x] 10.1 Run focused graph, Agent, memory, reflection-worker, auth, SSE/chat-run, semantic integration, and evaluation-harness tests and verify public memory APIs, reflection behavior, approval flow, artifact generation, and terminal SSE events are unchanged.
- [x] 10.2 Run `python -m pytest -q` and verify the default backend suite passes with model and integration markers excluded by project configuration.
- [x] 10.3 Run `python -m ruff check app tests` and `python -m ruff format --check app tests` and verify both style gates pass.
- [x] 10.4 Run the applicable real-model memory-retrieval evaluation against the configured local database, archive only sanitized evidence, and report `pass_rate`, `FAILED`, and `ERROR` separately.
- [x] 10.5 Run `openspec validate decouple-experience-memory-retrieval --strict` and verify the revised change artifacts pass strict validation before implementation is considered complete.

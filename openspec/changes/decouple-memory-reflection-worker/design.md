## Context

The main Graph currently routes normal chat, follow-up questions, teaching-plan approval, and artifact fan-in through `profile_memory_reflection_node`; it then optionally runs `experience_memory_reflection_node`. The functions are asynchronous but remain business dependencies, and `memory_reflection_goto` is carried in graph state to return to the intended route.

Chat runs already have a durable SQL row and a process-local manager, while long-term memory uses LangGraph's PostgreSQL Store through a separate autocommit connection pool. `finalize_chat_run` currently commits its own transaction. Manual memory endpoints call Store helpers directly, so they do not yet share concurrency or deletion rules with automatic reflection. See the proposal and `specs/background-memory-reflection/spec.md` for the behavioral boundary.

## Goals / Non-Goals

**Goals:**

- Make user-visible Graph boundaries independent from reflection model calls and Store writes.
- Persist deterministic, bounded reflection evidence, continue pending work after restart, and terminally fail work interrupted while running.
- Run one configured worker with a compact at-most-once job lifecycle, idempotent effects, and per-user conflict protection.
- Keep first-phase changes compatible with the current Store, API, retrieval logic, Windows deployment, and optional observability stack.
- Give tests and model evaluations a deterministic job-completion seam.

**Non-Goals:**

- Replacing LangGraph Store, introducing Redis as the source of truth, or adopting LangMem as a runtime dependency.
- Optimizing online retrieval, adding embeddings/reranking, refreshing memory on approval resume, or redesigning profile token budgets; those belong to phase two.
- Consolidation, expiry, knowledge graphs, or claims that generated teaching plans are classroom-validated experience.
- Adding a user-facing job API or new SSE event type.
- Running a separately packaged deployment unit or coordinating multiple active workers in this phase; the worker lifecycle is hosted by one designated backend process.

## Decisions

### 1. Use a PostgreSQL job table as the source of truth

Add a `memory_reflection_jobs` SQLAlchemy model with a stable job id, unique idempotency key, user/source identifiers, kind, business stage, extractor version, bounded JSON snapshot, evidence type, status, sanitized error category, timestamps, and optional applied-memory result metadata. Statuses are `pending`, `running`, `succeeded`, `skipped`, and `failed`.

The uniqueness key is derived from `(user_id, source_run_id, kind, business_stage, extractor_version)`. Duplicate registration becomes a no-op that returns the existing row. Redis may later wake workers but is not required for correctness.

Alternatives considered:

- Process-local tasks without a durable row: rejected because pending work would be lost on restart and evaluations would have no deterministic completion seam.
- Redis-only queue: rejected because current Redis is an event transport and should not become the sole memory durability layer.
- External task framework: deferred to avoid an operational dependency before workload justifies it.

### 2. Capture snapshots at the chat-run boundary, not inside reflection nodes

Delete the reflection nodes and `memory_reflection_goto` routing from the compiled Graph. At the end of streaming, the runtime builds job candidates from immutable run input plus a bounded projection of the current checkpoint state. Profile evidence is limited to the new user input from the run; approval-only resume runs do not repeat profile extraction. Experience evidence includes only the fields needed by the existing policy, such as a completed teaching plan and summarized successful artifact/revision results, with an explicit evidence type such as `generated_plan` or `generated_artifact`.

The manager passes candidates to the run finalization service. Eligible job rows and the terminal run transition are flushed in one SQLAlchemy transaction by removing the internal commit from the lower-level finalization operation. If checkpoint projection cannot be built, the user-facing run still finalizes: the deterministic profile candidate can still be registered from run input, while an unavailable experience candidate is omitted and observed as a sanitized scheduling failure. Database unavailability is already a failure of durable run finalization and is not made worse by the worker.

`waiting_approval` registers only a profile candidate. `succeeded` registers profile when the run has new input and experience only when the snapshot satisfies the current policy. Failed and cancelled runs never register experience work. A unique key prevents the same source input from being reflected again at multiple technical exits unless the business stage or extractor version intentionally differs.

Alternatives considered:

- Enqueue inside Graph nodes: rejected because it preserves memory side effects in the business graph and cannot share the run-finalization transaction.
- Read latest checkpoint in the worker: rejected because later turns and context compression can change the evidence.
- Store the full checkpoint: rejected for privacy, size, and coupling reasons.

### 3. Take work atomically with one at-most-once worker

Create a `MemoryReflectionWorker` with explicit `start()` and `stop()` methods registered in FastAPI lifespan after the Agent runtime is ready. Exactly one designated backend process enables this worker. Each poll takes the oldest `pending` job by atomically changing it to `running` with a conditional database update, commits that transition, and then performs extraction without holding a database transaction during the model call.

The worker makes one processing attempt. A model, storage, validation, or database error becomes terminal `failed` with a sanitized error category; a policy decision that produces no mutation becomes `skipped`. There is no `retry` state, backoff, attempt counter, lease owner, lease expiry, or automatic reclaim. On startup, the designated worker marks any leftover `running` jobs as terminal `failed` with category `worker_interrupted`, because the prior process cannot prove whether their work completed. Existing `pending` jobs remain eligible and are processed normally after restart.

The deployment MUST ensure only one process enables the worker, for example by setting `MEMORY_REFLECTION_WORKER_ENABLED=true` only on the designated instance. The conditional `pending -> running` update remains as a low-cost safety check against accidental duplicate polling, but it is not a lease or multi-worker coordination protocol.

Alternatives considered:

- Lease recovery and bounded retry: rejected for this phase because failed background reflection is acceptable and the extra state, timing, and fencing behavior are not justified by current requirements.
- Holding a database transaction during model calls: rejected because it would retain locks for an unbounded external call.

### 4. Introduce one mutation service and per-user serialization

Move automatic and manual memory mutations behind a `MemoryService`. Both paths acquire the same PostgreSQL transaction-scoped advisory lock derived from the account id before checking mutation guards and calling the Store. This limits concurrent updates for one user while allowing different users to proceed.

Add SQL mutation-guard records keyed by `(user_id, kind, memory_id)` with a monotonically increasing version, deletion generation/timestamp, last manual mutation time, and last applied job id. Memory payloads also carry the guard version and last job id. Manual API changes advance the guard; deletion leaves a tombstone rather than erasing conflict history. A background operation captures the target base version when it proposes an update and rechecks it under the lock before applying. A mismatch or a tombstone newer than the job evidence makes the operation `skipped` as stale. Automatic creates use a deterministic memory id derived from the job id, so replay cannot create a duplicate.

Because the SQL job/guard tables and LangGraph Store use separate connection pools, their writes cannot share one database transaction through current APIs. The protocol records enough identity on both sides for acknowledgement reconciliation: after acquiring the advisory lock, the worker checks the Store payload and guard for `last_applied_job_id`; if either proves the effect was applied, it repairs the other record and completes the job instead of applying again. Job completion is committed only after reconciliation. This protects idempotency around partial acknowledgements without scheduling another automatic processing attempt and is an explicit application-level saga, not claimed cross-store atomicity.

Alternatives considered:

- Keep direct Store writes: rejected because stale jobs can overwrite manual changes or revive deletions.
- Depend only on timestamps: rejected because clock ordering and equal timestamps do not provide a reliable concurrency token.
- Migrate all memory payloads into application tables now: deferred because it would combine the worker phase with a storage migration.

### 5. Keep extractors reusable and snapshots typed

Refactor the existing profile/experience reflection functions into extraction functions that accept typed snapshot data and return a normalized mutation proposal without writing. Preserve stable-signal gating, privacy sanitization, tool-call parsing, and existing prompts as far as possible. The worker then sends the proposal through `MemoryService`.

Snapshots and mutation proposals have explicit schema versions. Unknown versions fail terminally with a sanitized configuration category; extractor version changes intentionally produce a new idempotency domain without rewriting old jobs.

### 6. Test through service seams and job ownership

Unit tests cover registration uniqueness, snapshot bounds, atomic pending-to-running transition, startup failure of interrupted jobs, deterministic creates, stale updates, tombstones, and reconciliation after an acknowledgement gap. Graph tests assert no reflection nodes/routing state remain and chat finalization is independent of worker execution. Integration tests use PostgreSQL to verify atomic take, single-worker processing, concurrent manual mutations, and startup reconciliation.

The model evaluator receives the isolated source run id, waits through a job-service helper until only that run's jobs are terminal, then reads memory state. Timeout is explicit and reported separately. Offline tests use a deterministic fake extractor/Store and do not require real model calls.

### 7. Observe state transitions without content leakage

Use existing `log_observation`, `record_metric`, and tracing helpers for registration, take, skip, success, failure, queue depth, and latency. Metric dimensions are limited to job kind, state, and sanitized error category. IDs remain trace fields only where existing policy permits and never become metric labels; snapshots and memory content are never logged.

## Risks / Trade-offs

- [More than one backend process enables the worker] -> Document and configure one designated worker process; retain a conditional `pending -> running` update as accidental-duplication protection.
- [A process crashes after taking a job] -> Accept loss of that reflection attempt and mark leftover `running` jobs `failed` with `worker_interrupted` on the next startup.
- [Separate SQLAlchemy and LangGraph Store pools prevent atomic memory/job commits] -> Use deterministic ids, guard versions, `last_applied_job_id`, per-user advisory locks, and acknowledgement reconciliation.
- [Terminal run finalization now also inserts jobs] -> Keep candidate construction bounded and model-free; use one SQL transaction and make duplicate insertion a no-op.
- [Job snapshots increase database volume] -> Enforce per-kind size limits, retain only minimum projections, and provide a retention task for old terminal jobs.
- [Transient failures are not retried] -> Accept terminal background-memory failure in this phase and expose it through sanitized observations and evaluation results.
- [Existing direct helper callers can bypass safeguards] -> Keep low-level Store helpers internal to extraction/tests and migrate API and worker write paths to `MemoryService`; add tests that forbid direct production mutations.
- [Generated outputs may be mistaken for proven teaching experience] -> Persist an evidence type and keep prompts/content explicit that generated plans or artifacts are not classroom validation.

## Migration Plan

1. Add the job and mutation-guard models plus an idempotent startup migration compatible with existing `create_all` behavior.
2. Introduce configuration, job repository/service, typed snapshots, `MemoryService`, and the single worker behind a disabled-by-default or shadow registration switch for safe deployment testing.
3. Route manual memory API mutations through `MemoryService`, backfilling guard rows lazily from existing Store payloads.
4. Register jobs at chat-run terminal/approval boundaries and run the worker while the existing synchronous Graph reflection remains enabled; compare results without applying duplicate mutations in shadow mode.
5. Enable worker application, remove Graph reflection nodes/state/routing, and update evaluations to wait for jobs.
6. Designate exactly one worker-enabled backend process, verify startup reconciliation of interrupted jobs, and prune terminal jobs according to retention configuration.

Rollback disables registration and worker startup, then restores the prior Graph edges/state. Existing pending jobs remain inert and can be processed after forward recovery; the new tables are retained to avoid destructive rollback and duplicate replay.

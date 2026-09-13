## 1. Persistence and configuration

- [x] 1.1 Simplify the SQLAlchemy job model and migration to the `pending`/`running`/`succeeded`/`skipped`/`failed` state machine, removing attempt, availability, lease-owner, and lease-expiry fields while retaining uniqueness, snapshot, result, version, tombstone, and reconciliation data; verify model metadata and migration tests pass.
- [x] 1.2 Export the simplified models and update the idempotent PostgreSQL migration to remove obsolete lease/retry columns safely for fresh and already-migrated deployments; verify fresh creation and repeated startup.
- [x] 1.3 Simplify configuration to worker enablement, polling, snapshot limits, evaluation timeout, and terminal-job retention; remove lease, retry, attempt, and backoff settings and document that exactly one backend process enables the worker.

## 2. Typed reflection inputs and extraction

- [x] 2.1 Define versioned profile/experience job snapshot and normalized mutation-proposal schemas with strict size and field allowlists; verify oversize and prohibited fields are rejected or reduced deterministically.
- [x] 2.2 Add a model-free snapshot builder that uses immutable chat-run input plus a bounded checkpoint projection and records generated-plan/artifact evidence types; verify approval-only, failed, cancelled, compressed-context, and successful teaching-flow cases.
- [x] 2.3 Refactor current profile and experience reflectors into extraction-only functions that consume typed snapshots while retaining signal gating, tool-call parsing, evidence wording, and privacy sanitization; verify existing reflector unit cases pass without Store writes.

## 3. Job repository and lifecycle registration

- [x] 3.1 Implement job registration with the `(user, source run, kind, business stage, extractor version)` idempotency key and duplicate-return behavior; verify concurrent duplicate registrations create one row.
- [x] 3.2 Replace batched leased claims with an atomic single-job `pending -> running` transition; verify accidental concurrent pollers cannot both take the same job.
- [x] 3.3 Remove retry scheduling and implement immediate terminal failure with sanitized errors plus startup reconciliation that marks leftover `running` jobs `failed` as `worker_interrupted`; retain terminal-job cleanup tests.
- [x] 3.4 Change chat-run finalization to accept eligible job candidates and commit the terminal run transition plus job inserts in one SQLAlchemy transaction without changing terminal event semantics; verify waiting-approval, succeeded, failed, cancelled, and duplicate-finalization tests.
- [x] 3.5 Keep snapshot candidate construction in `ChatRunManager`, but isolate checkpoint lookup, candidate validation, and scheduling preparation failures so they cannot alter a completed or approval-paused run outcome; retain profile-only fallback when checkpoint projection is unavailable.

## 4. Safe memory mutation service

- [x] 4.1 Implement `MemoryService` for manual and automatic mutations with per-user PostgreSQL advisory locking and lazy guard backfill for existing Store memories; verify different users can proceed concurrently while one user's mutations serialize.
- [x] 4.2 Implement guard-version checks, manual-mutation precedence, deletion tombstones, and stale automatic-operation skipping; verify pending jobs cannot overwrite later API edits or recreate later API deletions.
- [x] 4.3 Implement deterministic automatic-create ids and `last_applied_job_id` reconciliation across SQL guards and Store payloads; verify repeated acknowledgement after each simulated gap produces exactly one memory effect without scheduling a new processing attempt.
- [x] 4.4 Route the existing create/update/delete memory endpoints through `MemoryService` without changing request or response schemas; verify API compatibility, ownership isolation, privacy behavior, version increments, and tombstones.
- [x] 4.5 Restrict production automatic/manual writes from bypassing `MemoryService` while retaining explicit low-level helpers for reads and isolated tests; verify a focused dependency or call-site test covers all production mutation paths.

## 5. Worker runtime and observability

- [x] 5.1 Simplify `MemoryReflectionWorker` to one-at-a-time polling, atomic take, one processing attempt, terminal failure, and bounded shutdown; verify pending jobs continue after restart while interrupted running jobs are failed and never re-executed.
- [x] 5.2 Start and stop the worker from FastAPI lifespan after Agent runtime initialization, supporting disabled and shadow modes for rollout; verify lifespan tests cover startup failure isolation and orderly shutdown.
- [x] 5.3 Emit job lifecycle logs, traces, queue/latency/interrupted-job metrics, and sanitized error categories through existing observability helpers; remove retry/attempt dimensions and verify only explicit lifecycle events affect job counters.

## 6. Remove synchronous Graph reflection

- [x] 6.1 Remove profile/experience reflection nodes, `memory_reflection_goto`, and their edges from Graph and state while routing normal chat, follow-up, plan review, and artifact fan-in directly to their existing business destinations; verify graph topology and approval-resume tests.
- [x] 6.2 Confirm online profile loading, experience retrieval, namespaces, privacy filtering, and pending-job non-blocking behavior remain unchanged; verify focused long-term-memory and Graph retrieval tests.

## 7. Evaluation and end-to-end verification

- [x] 7.1 Add a source-run-scoped job wait helper with explicit timeout and update the memory evaluator to await terminal jobs before reading after-state; verify timeout is distinguished from an incorrect completed mutation.
- [x] 7.2 Replace lease/retry integration tests with PostgreSQL coverage for atomic single-job take, one designated worker, interrupted-running startup failure, pending-job continuation, concurrent user sessions, manual edit conflicts, deletion during execution, and acknowledgement reconciliation.
- [x] 7.3 Re-run timing assertions showing approval and terminal run events are emitted without waiting for a blocked reflection extractor or failing snapshot preparation; verify both normal chat and artifact completion paths.
- [x] 7.4 After simplification, run `python -m pytest -q`, `python -m ruff check app tests`, `python -m ruff format --check app tests`, and `python -m tests.evals.cli validate-suite --expected-count 24` from `backend/`, fixing all failures within this change.
- [x] 7.5 After simplification, run the applicable memory model-evaluation category with local PostgreSQL, record first-token/approval/run-completion/background-visible latency separately, and verify any promoted evidence follows the benchmark redaction allowlist and reports pass rate rather than substituting average score.

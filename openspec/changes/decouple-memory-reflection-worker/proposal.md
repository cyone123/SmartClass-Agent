## Why

Long-term-memory reflection currently runs as synchronous nodes in the main LangGraph, so profile and experience maintenance can delay chat completion, approval prompts, and artifact completion. Moving reflection to a durable background path isolates memory failures from user-facing work while preserving queued work across process restarts; a job interrupted after processing starts is allowed to fail permanently.

## What Changes

- Remove profile and experience reflection from the user-facing Graph dependency chain while retaining the existing online profile loading and experience retrieval behavior.
- Persist bounded reflection inputs as PostgreSQL-backed memory jobs at explicit chat-run lifecycle boundaries instead of deriving them later from mutable thread state.
- Add one independently managed memory worker that atomically takes pending jobs and applies the existing reflection policies once; processing failures are terminal, and interrupted running jobs are marked failed on the next startup.
- Make job production and memory mutation idempotent, prevent stale automatic work from overwriting newer or explicitly deleted memories, and expose low-cardinality operational observations without introducing lease or retry machinery.
- Update memory evaluations and tests to wait for the relevant background job rather than assuming Graph completion implies reflection completion.
- Keep the existing `/api/memory` contract, memory namespaces, online retrieval flow, and PostgreSQL/LangGraph Store as the first-phase storage choices.

## Capabilities

### New Capabilities

- `background-memory-reflection`: Durable scheduling and worker execution of profile and experience reflection without blocking the user-facing Graph.

### Modified Capabilities

- None.

## Impact

- Backend Graph/state: reflection nodes and routing state are removed from the main execution path.
- Chat-run lifecycle: successful and approval-paused boundaries register the applicable reflection jobs without making SSE subscribers responsible for scheduling.
- Persistence: a new SQLAlchemy model/table and startup-compatible migration are added for a compact terminal job state machine, bounded source snapshots, idempotency keys, and applied-memory result metadata.
- Memory services/API: automatic and manual mutations share version/deletion safeguards while public memory endpoints remain compatible.
- Runtime: one designated FastAPI process starts and stops the in-process worker loop backed by durable PostgreSQL jobs; other application processes keep the worker disabled.
- Tests/evaluations/observability: add atomic-take, interrupted-job failure, deletion, idempotency, and non-blocking assertions; adapt model evaluations to await a specific job terminal state.

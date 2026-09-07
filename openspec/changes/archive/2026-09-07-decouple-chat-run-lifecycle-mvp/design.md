## Context

The current `POST /api/chat/stream` response generator owns the `AgentRuntime.stream_agent_events()` iterator. The Vue chat component aborts that fetch when the active session changes or the component unmounts, and `AgentRuntime` consequently cancels its producer task. PostgreSQL already stores LangGraph checkpoints, but it does not store an API-level run lifecycle or replayable UI events. Session history can recover committed messages and pending approvals, while in-flight token, progress, trace, suggestion, and error state is lost.

The repository already depends on PostgreSQL, SQLAlchemy, FastAPI lifespan state, and authenticated bearer-token requests. The MVP should reuse those pieces and the existing SSE event names without adding Redis, a broker, or a second deployment unit.

## Goals / Non-Goals

**Goals:**

- A submitted turn keeps running when every browser subscriber disconnects.
- A client can discover an active run for its thread and replay ordered events after a known cursor.
- Session switches and transient network failures can detach and later reattach without submitting the turn twice.
- Existing LangGraph checkpoints, approval interrupts, context compression, artifact persistence, storage abstraction, and SSE payload types remain authoritative.
- Run and subscription ownership is enforced by the existing user/thread authorization boundary.
- The implementation is testable without real models or external services.

**Non-Goals:**

- Surviving backend-process or host termination while an Agent call is in progress.
- Distributed worker leases, cross-process task claiming, automatic crash retry, dead-letter queues, or exactly-once execution.
- Making artifact generation fully idempotent across worker crashes.
- Replacing SSE with WebSocket or changing the LangGraph approval flow.
- Persisting events indefinitely or exposing raw run data through telemetry.

## Decisions

### Persist runs and events in PostgreSQL

Add `agent_runs` and `agent_run_events`. A run stores ownership, input references, lifecycle status, output-text snapshot, last sequence, and timestamps. Events use `(run_id, sequence)` ordering and JSON payloads. PostgreSQL is chosen because it is already mandatory and sufficient for the MVP; Redis Streams would add deployment and operational work before cross-process workers are required.

An event write locks the run row, increments `last_event_sequence`, inserts the event, and updates `output_text` for token events in one transaction. Token events are initially stored at the chunk granularity already produced by LangGraph. Batching is deferred until measured write volume proves it necessary.

### Use a process-owned task manager, independent from SSE subscribers

`ChatRunManager` owns `asyncio.Task` instances in FastAPI application state. The create-run endpoint commits a queued run, then schedules it through the manager. The task opens its own SQLAlchemy sessions, reloads attachment records, calls the existing `AgentRuntime.stream_agent_events()`, and persists every yielded event.

The manager does not attach task cancellation to an HTTP disconnect. Application shutdown cancels remaining tasks and marks unfinished runs failed on the next startup/reconciliation path. A dedicated worker and leases are intentionally deferred to the next reliability phase.

Alternative considered: merely stop cancelling the existing producer. This is rejected because its unbounded in-memory queue would continue growing without a subscriber and no event replay would be possible.

### Split submission from event subscription

`POST /api/chat/runs` validates the same message, thread, attachment, and approval rules as the legacy endpoint, creates a run, schedules it, and returns `202`. `GET /api/chat/runs/{run_id}` returns the authorized run snapshot. `GET /api/chat/runs/{run_id}/events` accepts `after_sequence` and/or `Last-Event-ID`, replays committed events, then polls for new events until the durable `done` event is observed. `GET /api/chat/runs/active?thread_id=...` supports remount and session-switch recovery. `POST /api/chat/runs/{run_id}/cancel` is the only browser action that requests execution cancellation.

The legacy `POST /api/chat/stream` remains available during migration and continues to use the existing direct-stream behavior. The Vue client moves to the new endpoints.

### Preserve event names and add sequence IDs

Existing `metadata`, `progress`, `token`, `artifact`, `artifact_trace`, `approval`, `suggestions`, `error`, and `done` handlers remain valid. SSE frames gain an `id` equal to the durable event sequence. The stored `done` payload contains `run_id` and final `status`; the frontend treats either this payload or legacy `[DONE]` as terminal.

### Keep lifecycle semantics aligned with LangGraph interrupts

Each user message or approval submission creates a new run. A run that emits an approval event ends as `waiting_approval`; it releases its task and is not considered active. An approval submission creates another run and resumes the existing LangGraph thread through the current `Command(resume=...)` path. Only `queued` and `running` runs are returned by active-run discovery.

The MVP rejects a second queued/running run for the same owned thread at submission time. The process-local Agent thread lock remains a second guard. A database partial-unique constraint is deferred because SQLite-independent testability and future distributed-worker semantics need a dedicated migration decision.

### Move frontend stream identity into per-thread Pinia state

The session store maintains run id, status, last event sequence, and subscription state per thread. Submitting a turn creates the run, stores its identity before subscribing, and consumes the replay endpoint with bearer-authenticated `fetch`. Network errors retry with bounded exponential backoff from the last sequence. Switching sessions aborts only the subscription. Returning to a thread queries its active run and reattaches; completed history and artifacts remain loaded through their existing APIs.

## Risks / Trade-offs

- [Risk] The backend process exits while a run is active, leaving a persisted `queued` or `running` row. → On startup, reconcile stale MVP rows to `failed` with a sanitized restart reason; phase two will replace this with leases and reclaim.
- [Risk] PostgreSQL receives many small token-event writes. → Keep payloads bounded, measure event-write rate, and add token coalescing only if needed.
- [Risk] A run finishes between history loading and active-run discovery. → The frontend reloads history after observing a terminal run and the event endpoint always replays through `done`.
- [Risk] Duplicate reconnect subscriptions deliver the same event. → Frontend and backend use monotonically increasing `(run_id, sequence)` cursors and ignore already-applied sequences.
- [Risk] Cancellation during artifact generation can leave an artifact row in `running`. → The MVP manager records run cancellation and refreshes artifact lists; artifact reconciliation and execution-key idempotency remain a phase-two task and are not claimed as solved here.
- [Risk] Storing request payloads duplicates conversation content. → Store only the message needed to execute the queued run plus attachment identifiers, scope access by user/thread ownership, omit it from event payloads and telemetry, and apply the same database retention controls as conversation state.

## Migration Plan

1. Deploy additive run/event tables and backend endpoints while retaining `/api/chat/stream`.
2. Deploy the Vue client using create-run plus replay SSE. Old backend clients remain compatible.
3. Monitor run completion/failure, event volume, active task count, and reconnect errors.
4. Roll back the frontend to `/api/chat/stream` if needed; additive tables and endpoints can remain unused without affecting LangGraph state.
5. After the MVP is stable, propose phase two for dedicated workers, leases, retries, artifact idempotency, and durable cancellation.

## Open Questions

- Event retention duration and compaction policy should be selected from observed run volume before production rollout.
- Phase two must decide whether to keep PostgreSQL polling/`LISTEN NOTIFY` or introduce a broker when workers become independent processes.

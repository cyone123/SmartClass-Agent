## Why

SmartClass currently drives the Agent directly inside the `/api/chat/stream` response lifecycle, so switching sessions, leaving the page, or losing network connectivity can cancel a still-running LangGraph turn and loses in-flight SSE state. The first delivery should let a browser detach and later reconnect to the same run while keeping the current graph, approval, artifact, and event contracts largely intact.

## What Changes

- Introduce a durable chat-run record with explicit `queued`, `running`, `waiting_approval`, `succeeded`, `failed`, and `cancelled` lifecycle states.
- Introduce an ordered, replayable run-event log for the existing `metadata`, `progress`, `token`, `artifact`, `artifact_trace`, `approval`, `suggestions`, `error`, and `done` events.
- Split chat submission from event consumption: a submission creates a run and returns immediately, while a separate authenticated SSE endpoint replays events from a sequence cursor and follows new events.
- Execute MVP runs in a backend-owned task that is independent from any individual SSE subscriber. Browser disconnects stop only the subscription; explicit cancellation remains a separate action.
- Allow the frontend to discover the active run for a thread, keep per-thread run cursors, and reconnect after session switches, component remounts, page reloads, or transient network failures.
- Preserve the current `/api/chat/stream` endpoint during migration as a compatibility surface where practical.
- Keep independent worker processes, leases, crash-safe retries, and complete cross-process idempotency out of this MVP; those remain a follow-up reliability phase.

## Capabilities

### New Capabilities

- `durable-chat-runs`: Persistent chat-run lifecycle, replayable SSE events, subscriber-independent execution, active-run discovery, explicit cancellation, and frontend reconnection behavior.

### Modified Capabilities

- `context-compression`: Define compression completion relative to the durable run lifecycle and replayable `done` event instead of the lifetime of one HTTP response.
- `external-observability`: Distinguish durable Agent run activity from short-lived SSE subscription activity while preserving redaction and low-cardinality rules.

## Impact

- Backend models and database initialization gain chat-run and run-event tables.
- Chat schemas, services, API routing, application lifespan, and Agent event publication are extended.
- The Vue chat panel and Pinia session/run state move from a single component-bound stream to per-thread run subscriptions and cursors.
- Existing SSE event payloads and LangGraph interrupt/checkpointer semantics remain compatible, but new event IDs and run-status payloads become authoritative for reconnect behavior.
- PostgreSQL stores queued input, output snapshots, and bounded replay events; raw prompt/completion content remains excluded from observability exports.
- Tests add disconnect, replay, authorization, duplicate-subscription, approval, and session-switch coverage.

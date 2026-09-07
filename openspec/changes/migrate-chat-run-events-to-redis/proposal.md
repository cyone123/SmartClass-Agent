## Why

The chat-run MVP persists every token and UI event through a PostgreSQL row lock, event insert, output-text update, and commit, while each SSE subscriber polls PostgreSQL four times per second. With no production run data to preserve yet, this is the lowest-risk point to move the high-frequency replay path directly to Redis Streams before the PostgreSQL event table becomes operationally expensive or migration compatibility becomes necessary.

## What Changes

- Replace PostgreSQL `agent_run_events` writes and polling reads with one Redis Stream per chat run and blocking `XREAD` replay/follow reads.
- Keep `agent_runs`, execution input, ownership, lifecycle status, terminal output snapshot, and LangGraph checkpoints in PostgreSQL; Redis holds retained UI events plus the live output/sequence projection.
- Preserve the existing integer SSE event IDs, `Last-Event-ID`/`after_sequence` behavior, event names, active-run discovery, explicit cancellation, and subscriber-independent in-process execution.
- Add configurable token-event coalescing so token chunks are persisted and delivered in bounded batches while state-changing events remain immediate.
- Add Redis persistence, retention, capacity, health, and observability configuration to the existing Docker deployment.
- Remove the PostgreSQL `AgentRunEvent` runtime path directly. There is no Event Store abstraction, dual-write mode, legacy-event reader, or historical-event backfill because the current environment has no run/event data that must be retained.
- Define an explicit terminal-finalization protocol across Redis event sequencing and PostgreSQL run status, including deterministic recovery of a missing terminal `done` entry from the PostgreSQL terminal snapshot.
- **BREAKING**: Redis becomes a required dependency for creating and following new durable chat runs; the backend does not fall back to PostgreSQL events when Redis is unavailable.
- Keep independent workers, leases, server-process crash recovery, automatic run retry, artifact execution idempotency, and broker-based job dispatch out of scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `durable-chat-runs`: Change retained run-event persistence, live snapshots, ordered replay, terminal finalization, and reconnect behavior from PostgreSQL event rows to Redis Streams without changing the user-facing SSE contract.
- `docker-deployment`: Make a persistent, non-evicting Redis service and its health/configuration requirements part of the supported deployment.
- `external-observability`: Add bounded Redis event-publish, replay, connection, retention, and failure signals without exposing high-cardinality or sensitive run content.

## Impact

- Backend models/services: remove `AgentRunEvent` persistence and PostgreSQL event polling; add direct Redis Stream publishing, live snapshot reads, token coalescing, terminal snapshot coordination, retention, and startup/shutdown handling.
- Backend API: keep the current chat-run endpoints and SSE payloads, but follow Redis with blocking reads and treat Redis availability as required for new runs.
- PostgreSQL: retain `agent_runs` as the lifecycle source of truth, stop high-frequency `output_text` and `last_event_sequence` updates during active execution, and remove or explicitly drop the empty `agent_run_events` table.
- Frontend: retain the current integer cursor and reconnect contract; only adapt if needed for explicit event-gap or Redis-unavailable responses.
- Deployment/configuration: add the Redis client dependency, a pinned Redis service with AOF and persistent storage, `noeviction`, health checks, retention and batching settings, and backend readiness checks.
- Tests/operations: add real-Redis integration coverage and benchmark PostgreSQL write reduction, Redis append/read latency, reconnect replay, multiple subscribers, retention, and terminal consistency.

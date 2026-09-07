## 1. Redis Dependency and Deployment

- [x] 1.1 Add centralized Redis URL, key prefix, operation timeout, reader-pool, active TTL, terminal retention, and token-batching settings plus `redis.asyncio` runtime dependency; verify configuration tests cover valid local/Docker values and fail clearly on invalid required settings.
- [x] 1.2 Add a pinned Redis Compose service with AOF, persistent volume, `noeviction`, internal-only networking, health check, and backend readiness dependency; verify `docker compose --env-file .env.docker config` succeeds and the running container reports the intended persistence and memory policy.
- [x] 1.3 Initialize and close dedicated Redis command and blocking-reader clients through backend lifespan without adding a generic Event Store abstraction; verify startup, shutdown, pool separation, timeout, and unavailable-Redis tests pass on Windows-compatible asyncio.
- [x] 1.4 Update Docker environment examples and deployment troubleshooting/hardening documentation for Redis capacity, AOF durability, backup, retention, connection pools, and non-eviction; verify documented variable names match the configuration layer and contain no real secrets.

## 2. Direct Redis Run-Event Operations

- [x] 2.1 Implement deterministic environment-prefixed per-Run stream, metadata, and output keys using the Run ID as the Redis Cluster hash tag; verify unit tests prove key colocation and prevent raw keys or Redis URLs from entering user-facing errors.
- [x] 2.2 Implement and load an atomic Lua append operation that increments the integer sequence, writes `<sequence>-0` stream entries, appends token output, and refreshes active expiry; verify concurrent append tests produce unique increasing sequences and exact output text.
- [x] 2.3 Implement direct Redis range/blocking reads that map public integer cursors to Stream IDs and decode only supported event payloads; verify replay tests cover cursor zero, mid-stream resume, bounded batches, malformed entries, and multiple independent readers.
- [x] 2.4 Implement live snapshot reads, terminal retention updates, key cleanup, and terminal `done` insertion at an explicit sequence; verify tests cover missing keys, idempotent terminal insertion, expiry application, and no active-stream `MAXLEN` trimming.
- [x] 2.5 Implement configurable adjacent-token coalescing in the in-process Run executor; verify tests prove time/size flushing, forced flush before every non-token event and exit path, exact final concatenation, and no reordering of progress/artifact/approval/error events.

## 3. PostgreSQL Lifecycle and Schema Cutover

- [x] 3.1 Change active Run serialization to overlay Redis live sequence/output while terminal Run serialization reads the PostgreSQL final snapshot; verify API/service tests cover active, terminal, missing-Redis-data, and unauthorized Run cases.
- [x] 3.2 Implement terminal finalization that flushes tokens, calculates a stable terminal sequence, commits status/output/error/timestamps/sequence in PostgreSQL, and then writes Redis `done`; verify fault-injection tests cover the PostgreSQL-before-Redis race and deterministic synthetic `done` behavior.
- [x] 3.3 Preserve startup reconciliation for orphaned in-process Runs using PostgreSQL terminal snapshots and Redis cleanup/terminal recovery without restarting Agent execution; verify a simulated backend restart marks stale queued/running Runs failed and exposes one logical terminal event.
- [x] 3.4 Remove the `AgentRunEvent` ORM model, relationship, PostgreSQL insert/query functions, and runtime event-table access; verify repository search and backend tests show no application dependency on `agent_run_events`.
- [x] 3.5 Add an explicit versioned schema upgrade that refuses to drop a non-empty `agent_run_events` table and drops it only after the empty-data precondition passes; verify the migration against real PostgreSQL for empty, missing, and unexpectedly populated table states.

## 4. ChatRunManager and API Integration

- [x] 4.1 Replace `ChatRunManager` per-event SQL transactions with direct Redis publishing while retaining process-owned tasks, explicit cancellation, approval status, and existing Agent event names; verify manager tests prove subscriber detach does not cancel execution and Redis append failure follows the documented failed-Run path.
- [x] 4.2 Gate `POST /api/chat/runs` on bounded Redis readiness before persisting or scheduling a Run and remove all PostgreSQL-event fallback behavior; verify unavailable Redis returns `503` with no created Run or Agent task.
- [x] 4.3 Replace the 250 ms database event polling loop with authorized blocking Redis reads, heartbeat timeouts, reconnect cursors, and terminal snapshot checks; verify SSE tests cover ordered replay, live follow, `Last-Event-ID`, multiple subscribers, disconnect, cancellation, and exactly one logical `done`.
- [x] 4.4 Preserve the current frontend integer cursor and per-thread reconnect flow, adding only explicit handling required for Redis readiness/unavailable responses or expired detailed history; verify `npm run test:chat-run` covers retry, snapshot restore, duplicate suppression, and terminal completion.
- [x] 4.5 Update Nginx routing and timeouts if required for the Redis-backed `/api/chat/runs/{run_id}/events` blocking stream; verify a proxied manual or automated stream receives heartbeats and incremental events without buffering.

## 5. Observability and Capacity Controls

- [x] 5.1 Add sanitized observations for Redis publish, snapshot, replay, blocking wait, retention, readiness, and failure operations; verify observability tests reject prompt/event content, credentials, Redis URLs/keys, run IDs, thread IDs, and user IDs from Prometheus labels.
- [x] 5.2 Add bounded metrics for append/read latency, batched token counts, payload sizes, active subscriptions, Redis failures, replay counts/gaps, and retention cleanup; verify the Prometheus endpoint exposes the metrics with only controlled low-cardinality labels.
- [x] 5.3 Add admission/capacity diagnostics for Redis write rejection and connection-pool exhaustion without silent event loss; verify injected `noeviction` OOM and exhausted-reader-pool cases produce explicit failure state, logs, and alerts rather than PostgreSQL fallback.

## 6. Integration, Performance, and Release Verification

- [x] 6.1 Add real PostgreSQL+Redis integration tests for append/replay, active snapshot overlay, terminal finalization, Redis restart with AOF, retention expiry, unavailable Redis, and stale in-process Run reconciliation; verify `python -m pytest -m integration` passes against the supported local Docker services.
- [x] 6.2 Extend chat-run load coverage to report events per Run, PostgreSQL statements/transactions avoided, Redis operations and latency, SSE connection count, replay latency, batching ratio, and memory per retained Run; verify the report demonstrates that active token streaming no longer performs event-frequency PostgreSQL writes or 250 ms event polling.
- [x] 6.3 Run backend regression and quality gates with `python -m pytest -q`, `python -m ruff check app tests`, and `python -m ruff format --check app tests`; verify all commands pass without enabling model or external integration tests implicitly.
- [x] 6.4 Run frontend `npm run test:chat-run` and `npm run build`; verify reconnect behavior and the production bundle both pass.
- [x] 6.5 Perform the coordinated cutover rehearsal: verify no active/data-bearing PostgreSQL event Runs, deploy Redis, drain submissions, apply the schema upgrade, deploy backend/frontend, reconnect after session switch and browser offline mode, and confirm Redis outage blocks new Runs without cancelling already detached subscriptions silently.
- [x] 6.6 Rehearse rollback by draining active Redis-backed Runs and restoring a compatible build/schema rather than switching live storage paths; document the observed steps and verify no rollback procedure claims to recover Redis-only detailed history through PostgreSQL.

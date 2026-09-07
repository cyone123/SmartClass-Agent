## Context

See `proposal.md` for motivation. The completed chat-run MVP already separates Agent execution from SSE subscribers, stores `agent_runs` and `agent_run_events` in PostgreSQL, and reconnects with integer `Last-Event-ID` cursors. Each emitted event currently opens a SQLAlchemy session, locks the Run row, increments its sequence, rewrites `output_text` for tokens, inserts an event, and commits. Each SSE subscription polls events and Run state every 250 ms.

There is no production Run/Event data to preserve, so this change can directly replace the PostgreSQL event path. PostgreSQL remains required for users, plans, sessions, Run ownership/input/status, LangGraph checkpoints, memory, RAG, and artifacts. Agent execution remains an in-process `asyncio.Task` owned by the single FastAPI process.

## Goals / Non-Goals

**Goals:**

- Remove token-frequency PostgreSQL transactions, Run-row locks, output rewrites, event inserts, and subscriber polling.
- Preserve the current chat-run API, integer event cursor, event payload semantics, explicit cancellation, approval flow, and subscriber-independent execution.
- Make Redis the only active/recent run-event transport, with replay, blocking follow, live output snapshots, bounded token batching, persistence, retention, and clear failure behavior.
- Keep a durable final Run snapshot in PostgreSQL so completed conversation output and status do not depend on Redis retention.

**Non-Goals:**

- No generic or swappable Event Store interface, PostgreSQL implementation, dual-write mode, shadow validation, legacy reader, or historical event backfill.
- No independent Worker, task queue, consumer group, lease, heartbeat, automatic retry, server-process crash continuation, or artifact execution-key work.
- No multi-FastAPI-worker or horizontal API deployment claim; process-local execution and cancellation maps still require one FastAPI worker.
- No exactly-once guarantee across Redis, PostgreSQL, LangGraph checkpoints, model calls, or artifact side effects.

## Decisions

### 1. Use Redis Streams directly from the chat-run path

Add a focused Redis integration module for chat-run event operations and inject its configured client into `ChatRunManager` and the chat API. The manager publishes directly to Redis and the SSE endpoint reads directly from Redis. Do not introduce a protocol with PostgreSQL and Redis implementations because there is no compatibility data or runtime fallback requirement.

Redis Pub/Sub is rejected because disconnected clients cannot replay missed messages. RabbitMQ queues are rejected because their competing-consumer and acknowledgement semantics fit job dispatch rather than independent UI replay. RabbitMQ Streams can replay but add a second protocol and more operational surface without improving this single-process phase.

### 2. Keep lifecycle truth in PostgreSQL and hot projections in Redis

`agent_runs` continues to own authorization, execution input, active-run conflicts, status transitions, error state, and terminal timestamps. During active execution, Redis owns:

- the retained ordered event stream;
- the current integer event sequence;
- the incrementally appended assistant output;
- terminal-sequence reservation metadata and retention timestamps.

Active Run lookup reads status/ownership from PostgreSQL and overlays Redis `last_sequence` and `output_text`. Terminal Run lookup uses the PostgreSQL snapshot only. PostgreSQL therefore changes a few times per Run rather than once per event.

### 3. Use one stream and colocated keys per Run

Derive keys without storing them in the database:

```text
sc:<environment>:chat-run:{<run_id>}:events
sc:<environment>:chat-run:{<run_id>}:meta
sc:<environment>:chat-run:{<run_id>}:output
```

The `{<run_id>}` hash tag keeps a Run's keys in one Redis Cluster slot if clustering is introduced later. The environment prefix prevents local, test, and deployed stacks from sharing keys. Redis keys and connection URLs must not appear in user errors or low-cardinality metric labels.

A global stream is rejected because every SSE subscription would have to scan/filter unrelated users' events. A stream per user or thread is rejected because Run cursors and retention boundaries would become coupled across turns.

### 4. Preserve integer SSE IDs with atomic Redis sequencing

Keep the public cursor as a positive integer. A Lua append operation atomically:

1. increments `last_sequence` in the Run metadata hash;
2. appends the event to the stream using explicit Redis ID `<sequence>-0`;
3. appends token text to the live output key when applicable;
4. refreshes the active-data expiry;
5. returns the integer sequence.

The SSE endpoint maps public cursor `N` to Redis ID `N-0` and continues to emit `id: N`. Explicit IDs avoid changing the frontend number parsing and deduplication contract. All user-visible subscribers use ordinary blocking `XREAD`, not `XREADGROUP`, so simultaneous subscribers each receive the complete sequence.

### 5. Coalesce only adjacent token events

Place a small token buffer inside the Run executor. Flush when the configurable time window or byte/character threshold is reached, before any non-token event, and before every exit path. The final concatenated output must be byte-for-byte equivalent after normal application string handling. Progress, artifact, trace, approval, suggestion, error, metadata, and terminal processing remain immediate.

Batching before Redis is preferred to batching inside SSE because it reduces storage, serialization, connection, and replay work consistently for all subscribers.

### 6. Replace database polling with blocking Redis reads

The event endpoint first authorizes the Run through PostgreSQL, then calls `XREAD BLOCK <heartbeat interval> COUNT <batch size>` from the supplied cursor. Returned entries are emitted in order. A block timeout produces the existing SSE keep-alive comment and gives the endpoint a chance to recheck PostgreSQL terminal state and client cancellation.

Use a dedicated Redis connection pool for blocking readers so waiting SSE requests cannot starve event publishers, health checks, or snapshot reads. Pool sizing and maximum concurrent subscriptions are configuration and capacity concerns. Closing an SSE request cancels only its blocking read; it does not cancel `ChatRunManager` execution.

### 7. Finalize PostgreSQL before exposing an authoritative terminal boundary

After the executor flushes buffered tokens:

1. read Redis `last_sequence` and live output;
2. calculate `terminal_sequence = last_sequence + 1` while the single Run writer is quiescent;
3. atomically commit PostgreSQL status, final output, error, completed time, and `last_event_sequence=terminal_sequence`;
4. append Redis `done` at explicit ID `<terminal_sequence>-0` with a conditional Lua operation that succeeds only when no later event exists;
5. apply terminal retention to all Run keys.

An SSE request that observes the PostgreSQL terminal snapshot before the Redis `done` append, or finds the terminal entry missing after a Redis failure, emits a deterministic synthetic `done` at the stored terminal sequence. If the real entry later appears, the existing sequence deduplication makes it the same logical event. This avoids requiring a distributed transaction while keeping PostgreSQL authoritative for completion.

The publisher must not emit a terminal `done` before the PostgreSQL terminal transaction succeeds. Failure to finalize PostgreSQL follows the existing in-process failure path and does not claim a completed Run.

### 8. Treat Redis as a required chat-run dependency

Before creating a Run, perform a bounded Redis readiness operation. If unavailable, return `503` and do not persist or schedule a Run. A race after readiness is handled by event-write retries. If a required append still fails, cancel the local execution, record a sanitized failed terminal snapshot in PostgreSQL using the latest locally known output, and allow the SSE endpoint to synthesize terminal completion once Redis is readable.

Do not fall back to PostgreSQL event writes: that would recreate two uncoordinated paths and make reconnect behavior depend on the failure moment. Health endpoints must distinguish liveness from readiness so an already-running process remains diagnosable while new Run admission is blocked.

### 9. Retain active events and expire terminal detail

Redis uses AOF, a persistent volume, and `noeviction`. Event keys receive a generous active TTL refreshed on every append so an abandoned stream eventually expires after an in-process crash. Successful terminal finalization changes all three keys to the configured reconnect retention period. The final PostgreSQL snapshot outlives Redis event detail.

Do not use blind `MAXLEN` trimming in this change because removing entries from an active replay window would require a new cursor-gap/reset protocol. Capacity is controlled through admission limits, event batching, retention, monitoring, and Redis memory sizing. Redis memory exhaustion must fail writes rather than silently discard replay data.

### 10. Remove the empty PostgreSQL event schema path

Remove `AgentRunEvent`, its ORM relationship, event insert/query functions, and runtime table usage. Add an explicit schema upgrade that checks the agreed empty-data precondition before dropping `agent_run_events`; do not depend on `Base.metadata.create_all()` to remove it. Keep `agent_runs.output_text` and `last_event_sequence`, but update them only at terminal finalization or stale-run reconciliation.

No `event_backend` discriminator is added because there are no legacy Runs to route and no supported fallback backend. Deployment is a coordinated cutover, not a rolling mixed-backend migration.

### 11. Keep existing security boundaries

Every status, active-run, cancellation, and SSE request continues to authorize against the PostgreSQL Run owner before Redis access. Redis values are never returned by key enumeration. Payloads keep the existing artifact-trace truncation and secret-redaction rules. Redis is reachable only on the internal application network in the supported Compose deployment.

## Risks / Trade-offs

- [Risk] Redis becomes mandatory and an outage blocks new chat runs. → Add readiness admission, bounded operation timeouts, clear `503` responses, persistent deployment, and explicit alerts; do not weaken the reconnect contract with a silent fallback.
- [Risk] A Redis blocking read consumes one pooled connection per active SSE subscription. → Use a dedicated reader pool, bound subscriptions, measure connection use, and size the pool from observed concurrency.
- [Risk] Redis and PostgreSQL terminal updates cannot be one transaction. → Commit a terminal sequence and final snapshot in PostgreSQL before publishing `done`, then synthesize the same sequence when the Redis terminal entry is absent.
- [Risk] AOF `everysec` can lose a short tail on Redis host failure. → Document that this phase guarantees user-side disconnect recovery, not infrastructure crash continuity; retain final output in PostgreSQL and allow stricter AOF policy later.
- [Risk] Per-Run streams and duplicate live-output storage consume memory. → Coalesce tokens, expire terminal keys, monitor bytes/events, reject writes under `noeviction`, and benchmark realistic traces before setting production capacity.
- [Risk] Removing the PostgreSQL event path makes rollback non-transparent after new Redis Runs exist. → Use a coordinated maintenance cutover, keep Redis-capable binaries available, and drain active Runs before rollback.
- [Risk] Backend process restart still terminates in-process Agent tasks. → Preserve the existing stale-Run failure reconciliation and explicitly defer workers, leases, and retries.

## Migration Plan

1. Verify and enforce the deployment precondition that no active Runs or retained PostgreSQL Run events require preservation.
2. Add centralized Redis configuration, async clients, Lua scripts, pinned Compose service, AOF volume, `noeviction`, health/readiness checks, and operational documentation.
3. Replace the manager's per-event SQL path with direct Redis publishing and token coalescing; keep local output accumulation for failure reporting.
4. Replace Run serialization overlays and SSE polling with Redis snapshot reads and blocking `XREAD`; preserve integer event IDs and frontend behavior.
5. Implement the terminal snapshot/sequence protocol and synthetic `done` fallback, then remove the `AgentRunEvent` model, relationship, queries, and PostgreSQL event writes.
6. Run an explicit schema upgrade that asserts the table is empty before dropping `agent_run_events`; do not perform destructive schema changes implicitly at application startup.
7. Validate with unit tests, real PostgreSQL+Redis integration tests, frontend reconnect tests, backend restart limitation tests, Redis restart tests, and event-volume/load benchmarks.
8. Deploy Redis first, stop new submissions, drain active Runs, apply the schema upgrade, deploy the backend/frontend cutover together, verify readiness and replay, then reopen submissions.

Rollback requires stopping new submissions and draining active Redis-backed Runs. Restore a Redis-capable application build whenever completed Redis Runs must remain replayable; reverting to the PostgreSQL-event implementation requires recreating its empty schema and accepts loss of Redis-only detailed event history. Do not attempt a configuration-only live rollback between the two storage paths.

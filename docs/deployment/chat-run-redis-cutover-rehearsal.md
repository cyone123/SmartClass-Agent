# Chat Run Redis Cutover Rehearsal

This is the execution record for the `migrate-chat-run-events-to-redis` coordinated cutover rehearsal. It supplements the reusable runbook in [docker.md](docker.md); it contains no credentials, object keys, prompts, or retained event payloads.

## Rehearsal Scope

- Date: 2026-09-07
- Host: Windows with Docker Desktop and Compose v2
- Services: PostgreSQL 16 with pgvector, Redis 7.4.5, backend and built frontend/Nginx image
- Admission state before cutover: zero `agent_runs` rows and no `agent_run_events` table
- Data policy: the local rehearsal account and failed model call are test-only; no production data was used

## Observed Cutover Results

| Check | Observed result |
| --- | --- |
| Compose validation | `docker compose --env-file .env.docker config --quiet` passed |
| Image build | `smartclass-backend:local` and `smartclass-frontend:local` built successfully |
| Redis policy | `appendonly=yes`, `appendfsync=everysec`, `maxmemory-policy=noeviction`, `maxmemory=512 MiB` |
| Redis restart | An acknowledged probe survived restart through AOF |
| Backend readiness | `/health` returned 200 and `/ready` returned 200 with Redis healthy |
| Schema precondition | `agent_runs` existed with zero rows; `agent_run_events` was absent |
| Versioned schema upgrade | `python -m app.migrations.v20260907_drop_agent_run_events` returned `missing` idempotently |
| Redis outage | `/health` stayed 200 while `/ready` returned 503; readiness returned 200 after Redis recovered |
| Lua cache loss | The first rehearsal exposed stale script SHA handling after Redis restart; the client now catches `NoScriptError`, reloads both scripts, and the repeated rehearsal passed |
| Proxied SSE | Nginx returned `text/event-stream`; a post-restart Run replayed ordered IDs 1–5 and one terminal `done` |
| Cursor reconnect | Reconnecting with `Last-Event-ID: 3` returned only IDs 4 and 5 and exactly one `done` |
| Frontend reconnect | Automated chat-run tests passed retry on Redis 503, snapshot restore, duplicate suppression, and terminal completion |
| Live load sample | Two completed Runs, 5 events/Run, 4 SSE connections, replay p50/p95 8.58/12.28 ms, 4,912 retained bytes/Run, and zero PostgreSQL event statements/transactions |
| External model | The rehearsal model call reached the provider but ended on the configured account's quota; transport still emitted ordered progress, error, and terminal events |

The full OnlyOffice image is not required for this event-store cutover. The already-built frontend/Nginx image was started with a temporary internal DNS stand-in solely to validate the chat Run proxy route; the stand-in was removed immediately after the SSE check.

The load sample's token batching ratio is `null` because the configured model quota prevented token fragments in these Runs. The deterministic batching tests still cover size, timer, boundary, and final flush behavior; the report does not invent a ratio for a zero-token sample.

## Coordinated Production Cutover

1. Stop or gate new Run submissions at the ingress.
2. Query PostgreSQL and require zero `queued`, `running`, or `waiting_approval` Runs. Require `agent_run_events` to be absent or empty.
3. Back up PostgreSQL and the Redis persistent volume, then start Redis and verify AOF plus `noeviction`.
4. Deploy the Redis-capable backend, wait for `/ready`, and run the versioned schema upgrade explicitly.
5. Deploy the matching frontend, create a canary Run, switch sessions, and reconnect with its last integer event ID. Simulate browser offline/online and verify the same cursor resumes without duplicates.
6. Stop Redis briefly in the maintenance environment: liveness must stay up, readiness/new admission must fail with 503, and clients must reconnect instead of treating transport EOF as Run completion.
7. Restore Redis, verify readiness and a new canary Run, then reopen submissions.

Do not run this as a rolling mixed-version deployment. There is no PostgreSQL event-row fallback or dual-write window.

## Observed Rollback Drill

The rehearsal frontend was stopped to close admission, PostgreSQL reported no active Runs, and the backend was recreated from a Redis-compatible image against the unchanged lifecycle schema. Redis AOF recovery and `/ready` were verified again. The empty/missing/populated migration states were also exercised transactionally against real PostgreSQL; the populated state was refused.

For an actual rollback:

1. Close admission and drain all active Redis-backed Runs before replacing any backend.
2. Preserve the Redis volume and restore a build that understands the Redis stream/schema contract.
3. If an older PostgreSQL-event build is unavoidable, recreate only the empty legacy table expected by that build and treat this as a separate schema operation. Do not point live traffic at two storage paths.
4. Validate terminal PostgreSQL snapshots and retained Redis replay independently before reopening admission.

PostgreSQL contains lifecycle state and the final output snapshot only. It cannot reconstruct Redis-only progress, token, artifact, approval, or error history, so no rollback procedure may claim otherwise.

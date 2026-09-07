# SmartClass Docker Deployment

This guide runs SmartClass with Docker Compose: Vue/Nginx frontend, FastAPI backend, PostgreSQL with pgvector, Redis, MinIO, OnlyOffice Document Server, OpenTelemetry Collector, Prometheus, and Grafana.

## Prerequisites

- Docker Engine or Docker Desktop with Compose v2.
- Network access from the backend container to your OpenAI-compatible model endpoints.
- Enough memory for PostgreSQL, MinIO, OnlyOffice, backend, and observability services. OnlyOffice is the heaviest service in the default stack.

## Environment Setup

Copy the example file and replace every placeholder secret:

```powershell
Copy-Item .env.docker.example .env.docker
```

The Compose file also loads `.env.docker` into the backend container through `env_file`, so keep the filename as `.env.docker` unless you also update `docker-compose.yml`. Passing `--env-file` alone is not enough to inject a differently named file into the backend service.

Key settings:

- `PUBLIC_API_BASE_URL` must be the browser-facing app origin. For local Compose with `FRONTEND_PORT=8080`, use `http://localhost:8080`.
- `DATABASE_URL` should point at `postgres:5432` inside Docker.
- `REDIS_URL` must point at `redis:6379` inside Docker. Redis is required for new durable chat runs.
- Size `REDIS_READER_POOL_SIZE` for the maximum concurrent SSE subscriptions and keep the command pool separate.
- `REDIS_ACTIVE_TTL_SECONDS` must exceed the longest supported run; `REDIS_TERMINAL_RETENTION_SECONDS` defines the detailed reconnect window.
- `STORAGE_BACKEND=minio` and `STORAGE_DOWNLOAD_MODE=proxy` are the recommended Docker defaults.
- `MINIO_ENDPOINT=minio:9000` is the backend's internal S3 endpoint.
- `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces` sends backend telemetry to the collector.
- `PROMETHEUS_ENABLED=true` exposes backend metrics at `/metrics` for Prometheus.

Do not commit `.env.docker`; it contains real secrets after setup.

## Start And Stop

Validate the Compose file:

```powershell
docker compose --env-file .env.docker config
```

Build and start:

```powershell
docker compose --env-file .env.docker up -d --build
```

Watch logs:

```powershell
docker compose --env-file .env.docker logs -f backend
```

Stop:

```powershell
docker compose --env-file .env.docker down
```

Stop and remove persistent data volumes only when you intentionally want a reset:

```powershell
docker compose --env-file .env.docker down -v
```

## Service URLs

With default ports:

- App: `http://localhost:8080`
- Backend health: `http://localhost:8000/health`
- Backend readiness: `http://localhost:8000/ready` (includes Redis)
- MinIO console: `http://localhost:9001`
- OnlyOffice direct access: `http://localhost:8082`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- OTel Collector OTLP HTTP: `http://localhost:4318`

Production deployments should expose only the frontend/ingress URL publicly. Database, Redis, MinIO, Prometheus, Grafana, and OTel ports should stay private or behind authenticated network controls. The Compose Redis service intentionally publishes no host port.

Host-side integration tests may add the loopback-only override; do not use it in production:

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.integration.yml up -d postgres redis
cd backend
python -m pytest -m integration
```

By default, `FRONTEND_BIND=0.0.0.0` and `DEBUG_BIND=127.0.0.1`. This means the app can be reached from outside the host if your firewall allows it, while backend, database, MinIO, OnlyOffice, Prometheus, Grafana, and OTel debug ports are bound to localhost only.

## Verification

Run the scripted infrastructure checks first:

```powershell
.\docker\verify.ps1
```

The script validates Compose config, builds the backend/frontend images, starts the stack, checks backend and frontend health, verifies the OnlyOffice script through the frontend origin, confirms the PostgreSQL `vector` extension, checks backend runtime tools, and confirms Prometheus/Grafana are reachable.

Then finish the user-flow checks:

1. Open `http://localhost:8080` and confirm the Vue app loads.
2. Call `http://localhost:8000/ready` or run:

   ```powershell
   docker compose --env-file .env.docker exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/ready').read().decode())"
   ```

3. Register or log in through the frontend.
4. Send a durable chat message and confirm `/api/chat/runs/{run_id}/events` replays integer event IDs and then follows incremental events.
5. Upload a knowledge file and confirm the backend logs show ingestion starting. MinIO should contain objects in the configured bucket.
6. Generate an artifact and verify the artifact download or HTML preview uses the frontend origin.
7. Open a DOCX/PPT/PDF preview and verify OnlyOffice loads from `/web-apps/apps/api/documents/api.js`.
8. Open Prometheus and check target `smartclass-backend` is up.
9. Open Grafana and confirm the Prometheus datasource works.
10. Verify Redis durability and capacity policy:

    ```powershell
    docker compose --env-file .env.docker exec redis redis-cli CONFIG GET appendonly appendfsync maxmemory-policy maxmemory
    docker compose --env-file .env.docker restart redis
    docker compose --env-file .env.docker exec redis redis-cli PING
    ```

    Expected values are `appendonly yes`, `appendfsync everysec`, and `maxmemory-policy noeviction`. Acknowledged writes can lose roughly the last AOF interval after host failure; use `appendfsync always` only after measuring the latency cost.

## Redis Event Retention And Backups

Redis retains active Run streams, metadata, and live output under a refreshed active TTL. Terminal Runs switch to the reconnect retention TTL; PostgreSQL retains the final output and lifecycle state after detailed events expire. Active streams are never `MAXLEN` trimmed.

Back up the `redis_data` volume together with PostgreSQL during a coordinated application pause. Test AOF restore regularly, monitor memory headroom, append/read latency, write rejections, pool exhaustion, active subscriptions, and retained bytes. `noeviction` is deliberate: memory exhaustion must reject writes instead of silently losing reconnectable events. Reduce retention or add capacity before raising admission limits.

The command pool serves publishing, snapshots, readiness, and retention operations. The separate reader pool dedicates one connection per blocking SSE read. Pool exhaustion and Redis OOM are explicit failures; SmartClass never falls back to PostgreSQL event rows.

## Storage Modes

Docker defaults to MinIO:

```env
STORAGE_BACKEND=minio
STORAGE_DOWNLOAD_MODE=proxy
```

Proxy download mode keeps authorization in the backend and avoids public/internal MinIO endpoint mismatches.

For troubleshooting or small local experiments, you can switch to local storage:

```env
STORAGE_BACKEND=local
FILE_STORAGE_ROOT=/app/storage
```

Keep the `backend_storage` volume mounted so local fallback files and workspace state survive container restarts.

## OnlyOffice URL Rules

OnlyOffice needs bidirectional reachability:

- Browser loads editor assets through the frontend Nginx origin.
- OnlyOffice fetches document URLs generated by the backend.
- OnlyOffice posts save callbacks back to the backend.

For local Compose, set:

```env
PUBLIC_API_BASE_URL=http://localhost:8080
```

For LAN testing, use a LAN-reachable host and port, for example:

```env
PUBLIC_API_BASE_URL=http://192.168.1.20:8080
```

For production, use the HTTPS app domain:

```env
PUBLIC_API_BASE_URL=https://smartclass.example.com
```

If document preview opens but saving fails, inspect backend logs for `/api/file/callback` and confirm OnlyOffice can resolve and reach `PUBLIC_API_BASE_URL`.

## Observability

The Docker stack includes:

- OpenTelemetry Collector at `otel-collector:4318` for backend OTLP export.
- Prometheus scraping `backend:8000/metrics`.
- Grafana with a provisioned Prometheus datasource and a starter SmartClass dashboard.

The backend still controls exports through environment variables:

```env
OTEL_ENABLED=true
PROMETHEUS_ENABLED=true
PROMETHEUS_METRICS_PATH=/metrics
```

Protect `/metrics`, Grafana, Prometheus, and collector ports in production. SmartClass observability code already redacts sensitive values and avoids high-cardinality Prometheus labels, but network exposure still matters.

## Troubleshooting

### Backend cannot connect to database

Check PostgreSQL health:

```powershell
docker compose --env-file .env.docker ps postgres
docker compose --env-file .env.docker logs postgres
```

Confirm `DATABASE_URL` uses `postgres:5432`, not `localhost`.

### Backend is live but not ready

Check Redis health and policy:

```powershell
docker compose --env-file .env.docker ps redis
docker compose --env-file .env.docker logs redis
docker compose --env-file .env.docker exec redis redis-cli INFO persistence
docker compose --env-file .env.docker exec redis redis-cli CONFIG GET maxmemory-policy
```

Confirm `REDIS_URL=redis://redis:6379/0` inside Compose. A `503` from new Run submission means Redis readiness failed; no Run row or Agent task is created.

### Missing vector extension

The stack mounts `docker/postgres/initdb/001-vector.sql`, which runs only when the PostgreSQL volume is first created. If you created the volume before adding the init script, apply it manually or recreate the volume:

```powershell
docker compose --env-file .env.docker exec postgres psql -U smartclass -d smartclass -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### MinIO bucket missing

Check the init service:

```powershell
docker compose --env-file .env.docker logs minio-init
```

It waits until MinIO accepts the configured credentials, then creates the configured `MINIO_BUCKET` idempotently.

### Model API calls fail

Backend containers cannot use host-only loopback endpoints. If your model gateway runs on the host, use a Docker-reachable address such as `host.docker.internal` on Docker Desktop, or expose the gateway on the LAN/private network.

### SSE responses arrive all at once

Confirm traffic goes through the provided Nginx config. The `/api/chat/stream` and `/api/chat/runs/{run_id}/events` locations disable proxy buffering and set long read timeouts.

### OnlyOffice editor does not load

Open `http://localhost:8080/web-apps/apps/api/documents/api.js`. If it fails, inspect frontend Nginx and OnlyOffice logs.

### OnlyOffice save callback fails

Confirm `PUBLIC_API_BASE_URL` is reachable from the OnlyOffice container and that the generated callback URL includes the access token query parameter.

### Runtime document and video tools missing

The backend Dockerfile installs `ffmpeg` and sets `VIDEO_FFMPEG_BIN=ffmpeg`. It also installs LibreOffice and Poppler for Office/PDF helper scripts. If video analysis fails, check:

```powershell
docker compose --env-file .env.docker exec backend ffmpeg -version
```

For document conversion helpers, check:

```powershell
docker compose --env-file .env.docker exec backend soffice --version
docker compose --env-file .env.docker exec backend pdftoppm -h
```

## Production Hardening

- Terminate TLS at a reverse proxy or ingress in front of the frontend service.
- Replace all placeholder passwords and JWT secrets.
- Do not expose PostgreSQL, MinIO API, Prometheus, Grafana, or OTel Collector publicly.
- Put Grafana behind SSO or strong credentials.
- Back up `postgres_data`, `minio_data`, and any required `backend_storage` contents.
- Back up and restore-test `redis_data`; keep AOF enabled and `maxmemory-policy=noeviction`.
- Alert on Redis OOM/write rejection, persistence errors, reader-pool exhaustion, and retained-data growth.
- Keep `STORAGE_DOWNLOAD_MODE=proxy` unless you have a deliberate public S3 endpoint strategy.
- Use lower `OTEL_TRACES_SAMPLER_ARG` values in high-traffic production environments.
- Consider separating long-running workers from the web backend before scaling beyond a single-node Compose deployment.

## Coordinated Event-Store Cutover And Rollback

This migration is not a rolling dual-write deployment. Before cutover, stop new submissions, verify no queued/running Runs and no rows in `agent_run_events`, deploy healthy Redis, and back up PostgreSQL. Run the empty-table-guarded upgrade:

```powershell
docker compose --env-file .env.docker exec backend python -m app.migrations.v20260907_drop_agent_run_events
```

Then deploy backend and frontend together, verify `/ready`, create a Run, reconnect once with `Last-Event-ID`, repeat after browser offline mode, and verify a Redis outage returns `503` for new submissions. Reopen submissions only after these checks pass.

Rollback also requires stopping submissions and draining every active Redis-backed Run. Restore a Redis-capable build/schema for retained detailed replay. A legacy PostgreSQL-event build requires recreating its empty event table and cannot recover Redis-only detailed history; never switch live storage paths through configuration alone.

See [chat-run-redis-cutover-rehearsal.md](chat-run-redis-cutover-rehearsal.md) for the dated execution record and observed failure/recovery checks.

## Context

The backend already reads configuration from the repository `.env` through `backend/app/config.py`, supports PostgreSQL via `DATABASE_URL` or `DB_*`, can switch storage through `STORAGE_BACKEND=local|minio`, and exposes optional OpenTelemetry and Prometheus configuration. The frontend uses same-origin `/api` for normal API calls, while development currently proxies `/api` to the backend and `/savefile` to an external OnlyOffice endpoint.

Docker deployment should therefore avoid changing the product contracts. It should make the existing contracts explicit at the deployment layer:

- Browser-facing traffic enters through the frontend Nginx container.
- Backend service-to-service traffic uses Docker service names.
- Persistent state lives in named volumes.
- Secret values stay in env files or deployment secret managers, not committed files.
- Prometheus labels and OTel exports keep the current redaction/cardinality rules.

## Goals / Non-Goals

**Goals:**

- Provide a single production-like Docker Compose stack for local or single-node deployment.
- Package backend dependencies needed by current runtime features: FastAPI, LangChain/LangGraph, PostgreSQL clients, MinIO client, OpenTelemetry/Prometheus libraries, ffmpeg, and Node.js/npm artifact-generation dependencies.
- Package frontend as static Vue assets served by Nginx.
- Use Nginx as the browser-facing reverse proxy for `/api`, SSE streams, file download/preview, and OnlyOffice-related paths.
- Use PostgreSQL with pgvector extension for app data, LangGraph checkpoint/store tables, and RAG vector storage.
- Use MinIO for new file/object storage in Docker while preserving backend proxy download mode by default.
- Run OTel Collector, Prometheus, and Grafana in the same stack with service-name based connectivity.
- Document how `PUBLIC_API_BASE_URL` must be set for OnlyOffice and public file URLs.

**Non-Goals:**

- Do not add Kubernetes, Helm, Terraform, or cloud provider-specific deployment in the first change.
- Do not replace the current backend configuration layer.
- Do not implement full production secret rotation, TLS automation, or multi-node high availability.
- Do not expose MinIO objects directly to browsers in the first Docker path; use backend proxy downloads by default.
- Do not add a vendor-specific observability backend to business code.

## Architecture

```text
Browser
  |
  v
frontend-nginx:80
  |-- /                  -> Vue dist
  |-- /api/*             -> backend:8000
  |-- /savefile/*        -> onlyoffice:80
  |-- OnlyOffice assets  -> onlyoffice:80

backend:8000
  |-- postgres:5432
  |-- minio:9000
  |-- otel-collector:4318

prometheus -> backend:8000/metrics
grafana    -> prometheus:9090
```

The browser should not need to know the backend container name. `frontend-nginx` is the public edge for the app. Backend-generated URLs should use `PUBLIC_API_BASE_URL` when a third-party service such as OnlyOffice needs to fetch a document or call back into the API. For simple local Compose, set it to the same browser-facing base URL, for example `http://localhost`.

## Service Design

### Backend Image

Use a Python slim base image with:

- Python dependencies from `backend/requirements.txt`.
- System packages required by the runtime, especially `ffmpeg` for video attachment analysis.
- Node.js/npm and `backend/package-lock.json` dependencies for existing PPT/DOCX generation scripts and workspace code execution.
- Working directory `/app`, with backend source copied under `/app`.
- Writable directory `/app/storage` mounted as a named volume for local storage fallback, observability JSONL traces, temporary materialization, and Agent workspace files.

The container command should run `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Health check can use `/health`.

### Frontend Image

Use a multi-stage build:

- Node stage runs `npm ci` and `npm run build` in `frontend`.
- Nginx stage serves `dist`.
- Nginx config reverse proxies:
  - `/api/` to `http://backend:8000/api/`
  - `/savefile/` to `http://onlyoffice/`
  - OnlyOffice browser asset paths to `http://onlyoffice/` if the editor script/assets are loaded through the same origin

SSE paths under `/api/chat/stream` must disable buffering and use long read timeouts.

### PostgreSQL

Use `pgvector/pgvector:pg16` or an equivalent pgvector-enabled PostgreSQL image. Add an init script:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The backend still creates application tables on startup through existing SQLAlchemy/LangGraph initialization, but the vector extension should exist before RAG table creation.

### MinIO

Use the official MinIO image with named volume persistence. Backend container configuration should use:

- `STORAGE_BACKEND=minio`
- `MINIO_ENDPOINT=minio:9000`
- `MINIO_BUCKET=smartclass`
- `MINIO_SECURE=false`
- `STORAGE_DOWNLOAD_MODE=proxy`

Bucket creation can be handled by a small `minio-mc` init service or documented as an operator step. Prefer an init service for reproducibility.

### OnlyOffice

OnlyOffice is optional at runtime for core chat, but needed for document preview/edit flows. Include it in Compose as a profile or normal service depending on startup cost.

The important URL rule is bidirectional reachability:

- Browser must load OnlyOffice editor assets.
- OnlyOffice must fetch backend document URLs.
- OnlyOffice must POST callback URLs back to the backend.

The simplest Compose path is to route browser-facing OnlyOffice traffic through frontend Nginx and set backend `PUBLIC_API_BASE_URL` to the same public app base URL. For production behind HTTPS, this should be the HTTPS domain.

### Observability

Backend environment in Docker should use:

- `OBSERVABILITY_ENABLED=true`
- `OTEL_ENABLED=true`
- `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces`
- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`
- `PROMETHEUS_ENABLED=true`
- `PROMETHEUS_METRICS_PATH=/metrics`

Prometheus should scrape `backend:8000` at `/metrics`, not `host.docker.internal`. Grafana should provision Prometheus as a datasource. OTel Collector should receive OTLP HTTP/gRPC and initially export debug traces, with optional Tempo wiring left as an example or profile.

## Environment Contract

Create `.env.docker.example` with Docker-safe defaults and placeholders for secrets:

- Database: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`.
- Auth: `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_SECONDS`.
- LLM/STT/vision/embedding model variables already used by backend.
- Storage: `STORAGE_BACKEND`, `MINIO_*`, `STORAGE_DOWNLOAD_MODE`.
- Public URLs: `PUBLIC_API_BASE_URL`.
- Runtime: `FILE_STORAGE_ROOT=/app/storage`, `VIDEO_FFMPEG_BIN=ffmpeg`, `WORKSPACE_EXECUTION_BACKEND=local` by default.
- Observability: `OTEL_*`, `PROMETHEUS_*`.

Do not commit real API keys, JWT secrets, MinIO secrets, or database passwords.

## Volumes And Ports

Recommended named volumes:

- `postgres_data`
- `minio_data`
- `backend_storage`
- `grafana_data`

Recommended local ports:

- `80` or `8080` for frontend Nginx
- `8000` optional backend direct access for debugging
- `5432` optional database debug access
- `9000` optional MinIO S3 API
- `9001` optional MinIO console
- `9090` Prometheus
- `3000` Grafana
- `4317/4318` optional OTel Collector debug access

For production, expose only the frontend/ingress and restrict metrics, database, MinIO, and collector ports to private networks.

## Risks / Trade-offs

- Backend image size will grow because it needs Python, Node.js, and ffmpeg. This is acceptable for the first Docker deployment because current artifact and video features need them; later optimization can split workers or use slimmer runtime layers.
- OnlyOffice networking is easy to misconfigure because document URLs must be reachable by both browser and Document Server. Mitigation: document `PUBLIC_API_BASE_URL` clearly and test file config/callback flows.
- MinIO presigned URLs can fail if internal and public endpoints differ. Mitigation: default Docker deployment to backend proxy download mode.
- Startup order alone does not guarantee readiness. Mitigation: add health checks and use retry-friendly backend initialization; avoid assuming `depends_on` means the database is fully ready unless health conditions are configured.
- Observability endpoints can leak operational data if exposed publicly. Mitigation: keep them on the internal Compose network by default and document production network protection.

## Migration Plan

1. Add Docker and Compose files without changing existing local development behavior.
2. Add Docker environment example and docs.
3. Add PostgreSQL pgvector init and MinIO bucket init.
4. Update observability example configs for Docker service names while preserving existing standalone docs.
5. Verify `docker compose config` and document full runtime verification steps.
6. Optionally add a later `compose.dev.yml` for source-mounted development after production-like deployment works.

Rollback strategy: keep existing local startup flow untouched. If Docker deployment has issues, operators can continue running backend/frontend/database using the current local environment while the Compose stack is corrected.

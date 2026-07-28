## 1. Backend Container

- [x] 1.1 Add `backend/Dockerfile` using a Python slim base image and installing backend Python dependencies from `requirements.txt`.
- [x] 1.2 Install runtime system dependencies required by current features, including `ffmpeg` and Node.js/npm.
- [x] 1.3 Install backend Node dependencies from `backend/package-lock.json` for PPT/DOCX generation scripts.
- [x] 1.4 Configure backend container working directory, Python path, writable `/app/storage`, and `uvicorn app.main:app --host 0.0.0.0 --port 8000` command.
- [x] 1.5 Add backend `.dockerignore` to exclude `.venv`, caches, local storage payloads, node_modules, test outputs, and local secrets.

## 2. Frontend Container And Nginx

- [x] 2.1 Add `frontend/Dockerfile` with a Node build stage using `npm ci && npm run build`.
- [x] 2.2 Add an Nginx runtime stage that serves the Vue `dist` output.
- [x] 2.3 Add Nginx config for SPA fallback, `/api` reverse proxy to backend, and SSE-friendly buffering/timeouts.
- [x] 2.4 Add Nginx proxy rules for OnlyOffice `/savefile` and required editor/static asset paths.
- [x] 2.5 Add frontend `.dockerignore` to exclude node_modules, dist, caches, and local editor metadata.

## 3. Compose Stack

- [x] 3.1 Add root-level `docker-compose.yml` defining frontend, backend, postgres, minio, minio bucket init, onlyoffice, otel-collector, prometheus, and grafana services.
- [x] 3.2 Add service health/readiness checks for backend `/health`, PostgreSQL, MinIO bucket initialization, Prometheus, and Grafana where practical.
- [x] 3.3 Configure Compose networks so only frontend is browser-facing by default and internal services communicate by service name.
- [x] 3.4 Add named volumes for PostgreSQL, MinIO, backend storage, and Grafana state.
- [x] 3.5 Keep direct debug port mappings optional or clearly marked so production exposes only the frontend/ingress path.

## 4. Database And Storage Initialization

- [x] 4.1 Add PostgreSQL init SQL that creates the `vector` extension before RAG vector table initialization.
- [x] 4.2 Use a pgvector-enabled PostgreSQL image in Compose.
- [x] 4.3 Add a MinIO client init service that creates the configured bucket idempotently.
- [x] 4.4 Set Docker defaults to `STORAGE_BACKEND=minio` and `STORAGE_DOWNLOAD_MODE=proxy`.
- [x] 4.5 Document how to switch back to local storage for development or troubleshooting.

## 5. Environment And Public URL Configuration

- [x] 5.1 Add `.env.docker.example` with Docker service-name defaults and placeholders for secrets.
- [x] 5.2 Include all required LLM, structured model, embeddings, STT, video vision, JWT, database, storage, workspace, and observability variables.
- [x] 5.3 Document `PUBLIC_API_BASE_URL` for local Compose, LAN testing, and production HTTPS domains.
- [x] 5.4 Ensure existing `.env` remains usable for non-Docker local development.
- [x] 5.5 Avoid committing real API keys, JWT secrets, database passwords, or MinIO credentials.

## 6. Observability Stack

- [x] 6.1 Add Docker-specific OpenTelemetry Collector config that receives OTLP HTTP/gRPC from backend service names.
- [x] 6.2 Add Docker-specific Prometheus config scraping `backend:8000/metrics`.
- [x] 6.3 Add Grafana datasource provisioning for Prometheus.
- [x] 6.4 Add a minimal Grafana dashboard or dashboard notes for HTTP latency, chat runs, LLM calls/tokens, tool failures, artifact failures, file ingestion failures, storage failures, and workspace execution failures.
- [x] 6.5 Keep OTel and Prometheus controlled by existing `OTEL_ENABLED` and `PROMETHEUS_ENABLED` environment variables.

## 7. Documentation

- [x] 7.1 Add `docs/deployment/docker.md` describing prerequisites, environment setup, startup, shutdown, logs, and health checks.
- [x] 7.2 Document service URLs for app, backend health, MinIO console, Prometheus, and Grafana.
- [x] 7.3 Document common troubleshooting cases: database not ready, missing vector extension, MinIO bucket missing, model API connectivity, OnlyOffice callback failure, SSE buffering, and ffmpeg missing.
- [x] 7.4 Add production hardening notes for TLS, secrets, network exposure, metrics protection, backups, and volume persistence.
- [x] 7.5 Cross-link the Docker deployment guide from existing observability docs.
- [x] 7.6 Add a Windows-friendly Docker verification script for build, startup, health, pgvector, runtime tools, Prometheus, and Grafana checks.

## 8. Verification

- [x] 8.1 Run `docker compose config` to validate Compose syntax.
- [x] 8.2 Build backend and frontend images.
- [x] 8.3 Start the stack and verify backend `/health`.
- [x] 8.4 Verify frontend can log in, call `/api`, and consume `/api/chat/stream` SSE without proxy buffering.
- [x] 8.5 Verify knowledge file upload writes through MinIO and RAG ingestion can initialize the vector table.
- [x] 8.6 Verify artifact download/HTML preview works through the frontend origin.
- [x] 8.7 Verify OnlyOffice config produces reachable document and callback URLs when OnlyOffice is enabled.
- [x] 8.8 Verify Prometheus scrapes backend metrics and Grafana can query Prometheus.

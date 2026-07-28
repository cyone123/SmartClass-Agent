## Why

SmartClass currently has the main product flow, MinIO-backed storage option, and OpenTelemetry/Prometheus observability primitives in place, but deployment is still mostly implicit: developers run the backend, frontend, database, object storage, OnlyOffice, and observability tools through local machine state. This makes environment setup fragile, especially on Windows, and makes production-like validation of SSE, file preview, MinIO, RAG vector storage, and observability harder than it needs to be.

The project needs a Docker deployment path that preserves the existing API/storage/observability contracts while giving operators one reproducible way to start the frontend, backend, PostgreSQL/pgvector, MinIO, OnlyOffice Document Server, OpenTelemetry Collector, Prometheus, and Grafana.

## What Changes

- Add Docker build definitions for the FastAPI backend and Vue frontend.
- Add a production-oriented Docker Compose stack for backend, frontend Nginx, PostgreSQL with pgvector, MinIO, OnlyOffice, OpenTelemetry Collector, Prometheus, and Grafana.
- Add Nginx reverse proxy configuration so the browser uses one origin for Vue static assets, `/api` requests, SSE streams, HTML preview, file download, and OnlyOffice command/static paths.
- Add Docker-specific environment examples that map existing backend variables to container service names such as `postgres`, `minio`, and `otel-collector`.
- Add database initialization for the pgvector extension required by the RAG vector store.
- Add Docker-ready observability configs and Grafana provisioning for Prometheus-based dashboards, while keeping OpenTelemetry and Prometheus optional through existing backend settings.
- Document startup, health checks, required secrets, local development differences, and production hardening notes.

## Capabilities

### New Capabilities

- `docker-deployment`: Run SmartClass through a reproducible Docker Compose stack covering app services, persistence, object storage, document preview, and observability.

### Modified Capabilities

- `external-observability`: Reuse the existing OTel and Prometheus support from inside the Docker network.
- `object-storage`: Reuse the existing MinIO storage backend through service-name based configuration.

## Impact

- Deployment files: root-level Compose file(s), backend Dockerfile, frontend Dockerfile, Nginx config, `.dockerignore` files, and Docker environment examples.
- Backend runtime image: must include Python dependencies, Node.js/npm for existing skill-generated artifacts, ffmpeg for video attachment analysis, and a stable writable storage/workspace directory.
- Frontend runtime image: must serve built Vue assets and reverse proxy `/api`, SSE streams, OnlyOffice routes, and optional metrics/internal paths appropriately.
- Database: Compose should use a pgvector-enabled PostgreSQL image and initialize the `vector` extension before backend startup relies on RAG.
- Storage: Compose should use MinIO by default for new object storage while retaining local backend fallback for development.
- Observability: Compose should update Prometheus scrape targets to `backend:8000`, configure backend OTLP endpoint to `otel-collector:4318`, and provision Grafana datasources.
- Docs: add an operator-facing Docker deployment guide with secrets, ports, volumes, health checks, troubleshooting, and production notes.

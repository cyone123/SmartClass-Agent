## ADDED Requirements

### Requirement: Compose stack provides all runtime services
The system SHALL provide a Docker Compose stack that can run the SmartClass frontend, backend, PostgreSQL with pgvector, MinIO, OnlyOffice Document Server, OpenTelemetry Collector, Prometheus, and Grafana with service-name based internal connectivity.

#### Scenario: Start production-like stack
- **WHEN** an operator starts the Docker Compose stack with a Docker environment file based on the provided example
- **THEN** Compose creates app, persistence, object storage, document preview, and observability services on the expected internal network

#### Scenario: Backend reaches internal dependencies
- **WHEN** the backend container starts inside the Compose network
- **THEN** it MUST connect to PostgreSQL, MinIO, and the OpenTelemetry Collector using Docker service names rather than host-local addresses

### Requirement: Frontend edge serves app and proxies backend traffic
The system SHALL serve the Vue frontend through Nginx and proxy browser-facing API, SSE, file, HTML preview, and OnlyOffice-related requests through the same public origin.

#### Scenario: API requests use same origin
- **WHEN** the browser calls frontend routes or `/api` endpoints through the Nginx container
- **THEN** Vue assets are served by Nginx and API requests are proxied to the backend without requiring the browser to know the backend service name

#### Scenario: Chat stream is not buffered
- **WHEN** the browser consumes `/api/chat/stream`
- **THEN** Nginx MUST preserve streaming behavior with buffering disabled and timeouts suitable for long-running Agent runs

### Requirement: Backend image contains required runtime dependencies
The backend container image SHALL include Python dependencies, Node.js/npm artifact-generation dependencies, ffmpeg, and a writable storage/workspace directory required by existing SmartClass backend features.

#### Scenario: Video and artifact features run in container
- **WHEN** a user triggers video attachment analysis or artifact generation inside the backend container
- **THEN** the backend can invoke ffmpeg and existing Node/Python skill dependencies without relying on host-installed tools

#### Scenario: Runtime state is writable
- **WHEN** backend features create temporary files, local fallback objects, JSONL traces, or Agent workspace files
- **THEN** those files are written under the configured container storage root and can be persisted through a Compose volume

### Requirement: Database initializes vector capability
The Docker deployment SHALL use a PostgreSQL image with pgvector support and initialize the `vector` extension before RAG vector table initialization is required.

#### Scenario: RAG runtime initializes vector table
- **WHEN** the backend creates or opens the RAG vector store during startup
- **THEN** the database supports vector columns and the vector table can be initialized without manual database patching

### Requirement: MinIO storage is reproducible
The Docker deployment SHALL configure MinIO as the default object storage backend for Docker and create the configured bucket idempotently.

#### Scenario: Object storage bucket exists
- **WHEN** the Compose stack starts with MinIO enabled
- **THEN** the configured bucket exists before normal file upload, artifact generation, or download flows need it

#### Scenario: Downloads remain authenticated through backend
- **WHEN** Docker deployment uses MinIO for stored files
- **THEN** download and preview flows MUST use backend proxy mode by default so user authorization and endpoint consistency are preserved

### Requirement: Public URL configuration supports OnlyOffice
The Docker deployment SHALL document and configure `PUBLIC_API_BASE_URL` so OnlyOffice can fetch document URLs and post save callbacks to a reachable SmartClass API endpoint.

#### Scenario: OnlyOffice opens a document
- **WHEN** the frontend requests an OnlyOffice config for a supported file
- **THEN** the generated document URL is reachable by the OnlyOffice service and remains protected by the existing access token mechanism

#### Scenario: OnlyOffice saves a document
- **WHEN** OnlyOffice posts a save callback
- **THEN** the callback URL resolves to the backend API and the backend can write the updated file through the configured storage service

### Requirement: Observability stack uses Docker service names
The Docker deployment SHALL configure backend telemetry, Prometheus scraping, and Grafana provisioning using Docker service names and the existing observability environment variables.

#### Scenario: Prometheus scrapes backend metrics
- **WHEN** `PROMETHEUS_ENABLED=true` in the backend container
- **THEN** Prometheus scrapes the backend metrics endpoint at `backend:8000` using the configured metrics path

#### Scenario: Backend exports OTLP telemetry
- **WHEN** `OTEL_ENABLED=true` in the backend container
- **THEN** the backend exports OTLP telemetry to the OpenTelemetry Collector service without hard-coding a vendor backend in application code

#### Scenario: Grafana can query Prometheus
- **WHEN** Grafana starts in the Compose stack
- **THEN** it has a provisioned Prometheus datasource suitable for SmartClass operational dashboards

### Requirement: Docker configuration keeps secrets out of source control
The system SHALL provide Docker environment examples with safe defaults and placeholders while excluding real secrets, local storage payloads, build outputs, and dependency folders from Docker build contexts.

#### Scenario: Operator prepares environment
- **WHEN** an operator copies the Docker environment example and fills required values
- **THEN** the resulting environment can configure database credentials, JWT secret, model API credentials, MinIO credentials, public URL, storage, workspace, and observability settings

#### Scenario: Docker build context excludes local state
- **WHEN** backend or frontend images are built
- **THEN** Docker ignore rules prevent local virtual environments, node_modules, generated dist files, caches, local storage payloads, and local secret files from being sent unnecessarily

### Requirement: Deployment guide documents operation and hardening
The system SHALL include Docker deployment documentation covering startup, shutdown, service URLs, health checks, verification, troubleshooting, and production hardening.

#### Scenario: Operator validates deployment
- **WHEN** an operator follows the Docker deployment guide
- **THEN** they can verify backend health, frontend API access, SSE streaming, MinIO storage, RAG vector initialization, artifact preview/download, OnlyOffice callbacks, Prometheus scraping, and Grafana datasource connectivity

#### Scenario: Operator prepares production
- **WHEN** an operator adapts the Compose stack for production
- **THEN** the guide identifies required hardening for TLS, secrets, network exposure, metrics protection, backups, persistent volumes, and public URL configuration

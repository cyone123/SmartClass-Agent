## MODIFIED Requirements

### Requirement: Compose stack provides all runtime services
The system SHALL provide a Docker Compose stack that can run the SmartClass frontend, backend, PostgreSQL with pgvector, Redis, MinIO, OnlyOffice Document Server, OpenTelemetry Collector, Prometheus, and Grafana with service-name based internal connectivity.

#### Scenario: Start production-like stack
- **WHEN** an operator starts the Docker Compose stack with a Docker environment file based on the provided example
- **THEN** Compose creates app, relational persistence, Redis event persistence, object storage, document preview, and observability services on the expected internal network

#### Scenario: Backend reaches internal dependencies
- **WHEN** the backend container starts inside the Compose network
- **THEN** it MUST connect to PostgreSQL, Redis, MinIO, and the OpenTelemetry Collector using Docker service names rather than host-local addresses

### Requirement: Frontend edge serves app and proxies backend traffic
The system SHALL serve the Vue frontend through Nginx and proxy browser-facing API, SSE, file, HTML preview, and OnlyOffice-related requests through the same public origin.

#### Scenario: API requests use same origin
- **WHEN** the browser calls frontend routes or `/api` endpoints through the Nginx container
- **THEN** Vue assets are served by Nginx and API requests are proxied to the backend without requiring the browser to know the backend service name

#### Scenario: Chat stream is not buffered
- **WHEN** the browser consumes `/api/chat/runs/{run_id}/events` or the compatibility chat stream
- **THEN** Nginx MUST preserve streaming behavior with buffering disabled and timeouts suitable for long-running Agent runs and Redis blocking reads

### Requirement: Deployment guide documents operation and hardening
The system SHALL include Docker deployment documentation covering startup, shutdown, service URLs, health checks, verification, troubleshooting, and production hardening for all required services including Redis event persistence.

#### Scenario: Operator validates deployment
- **WHEN** an operator follows the Docker deployment guide
- **THEN** they can verify backend health, Redis persistence and non-eviction configuration, frontend API access, chat-run replay, MinIO storage, RAG vector initialization, artifact preview/download, OnlyOffice callbacks, Prometheus scraping, and Grafana datasource connectivity

#### Scenario: Operator prepares production
- **WHEN** an operator adapts the Compose stack for production
- **THEN** the guide identifies required hardening for TLS, secrets, network exposure, metrics protection, PostgreSQL and Redis backups, persistent volumes, capacity limits, and public URL configuration

## ADDED Requirements

### Requirement: Redis event persistence is restart-safe and non-evicting
The Docker deployment SHALL configure Redis with append-only persistence, a persistent data volume, health checks, and a non-evicting memory policy suitable for reconnectable chat-run events.

#### Scenario: Redis container restarts
- **WHEN** the Redis container restarts after acknowledged event writes
- **THEN** it MUST recover retained stream entries according to the documented append-only persistence durability window

#### Scenario: Redis reaches its configured memory limit
- **WHEN** retained event data exhausts the configured Redis memory allowance
- **THEN** Redis MUST reject new writes rather than silently evict active or reconnectable run events

#### Scenario: Backend starts without healthy Redis
- **WHEN** the required Redis service is unavailable or misconfigured
- **THEN** backend readiness MUST report the dependency failure and new chat runs MUST NOT start without replayable event storage

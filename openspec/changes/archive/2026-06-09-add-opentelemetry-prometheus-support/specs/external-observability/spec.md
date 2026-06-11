# external-observability Specification

## ADDED Requirements

### Requirement: Configurable external observability exporters

The system SHALL allow backend configuration to enable or disable OpenTelemetry and Prometheus exports independently while preserving existing logging and JSONL observation behavior.

#### Scenario: Exporters are disabled

- **WHEN** OpenTelemetry and Prometheus export configuration is disabled
- **THEN** the backend MUST continue to emit existing structured logging and optional JSONL observation events without requiring external telemetry services

#### Scenario: OpenTelemetry is enabled

- **WHEN** OpenTelemetry export is enabled with a valid service name and OTLP endpoint configuration
- **THEN** the backend MUST initialize OpenTelemetry providers and export FastAPI and SmartClass application telemetry to the configured endpoint

#### Scenario: Prometheus is enabled

- **WHEN** Prometheus export is enabled
- **THEN** the backend MUST expose a Prometheus-compatible metrics endpoint at the configured path

#### Scenario: Explicit exporter configuration is invalid

- **WHEN** an external exporter is explicitly enabled but required configuration is missing or invalid
- **THEN** backend startup or exporter initialization MUST fail with a clear configuration error

### Requirement: FastAPI and SmartClass trace export

The system SHALL export traces for HTTP requests and SmartClass Agent workflow observations using sanitized correlation metadata.

#### Scenario: HTTP request is handled

- **WHEN** the backend handles a FastAPI request
- **THEN** OpenTelemetry instrumentation MUST create request trace data that includes route, method, status, and duration metadata without logging credentials

#### Scenario: Agent workflow event is observed

- **WHEN** SmartClass emits an observation event for chat runs, graph nodes, LLM calls, tool calls, RAG retrieval, workspace execution, storage operations, memory operations, or artifact generation
- **THEN** the OpenTelemetry exporter MUST attach sanitized SmartClass attributes including run id, thread id, plan id, agent name, event name, status, duration, and error category when available

#### Scenario: Sensitive content is present

- **WHEN** observation fields contain credentials, JWTs, access tokens, presigned URL signatures, host paths, full prompt text, full attachment text, full memory content, or other sensitive values
- **THEN** exported trace attributes MUST redact or omit those values according to the existing SmartClass sanitization policy

### Requirement: Prometheus metrics export

The system SHALL expose low-cardinality Prometheus metrics for SmartClass system health, Agent behavior, and long-running workflow outcomes.

#### Scenario: Agent and system observations are recorded

- **WHEN** SmartClass records observations for chat runs, LLM calls, tool calls, RAG retrieval, file ingestion, artifact generation, workspace code execution, or storage operations
- **THEN** Prometheus metrics MUST update counters, histograms, or gauges with bounded labels suitable for aggregation and alerting

#### Scenario: Metric labels are generated

- **WHEN** Prometheus labels are generated from an observation event
- **THEN** labels MUST NOT include high-cardinality or sensitive values such as run id, thread id, user id, filenames, object keys, URLs, prompt text, completion text, attachment text, or memory content

#### Scenario: Token usage is available

- **WHEN** an LLM observation includes token usage metadata
- **THEN** Prometheus metrics MUST record input, output, and total token counts using bounded labels such as model and token type

#### Scenario: Active chat runs change

- **WHEN** a chat stream run starts, completes, or fails
- **THEN** Prometheus metrics MUST expose an active run gauge or equivalent metric that reflects current backend run activity

### Requirement: Exporter failure isolation

The system SHALL ensure external telemetry export failures do not break user-facing SmartClass workflows.

#### Scenario: Runtime telemetry export fails

- **WHEN** an OpenTelemetry or Prometheus sink raises an exception while emitting an observation event
- **THEN** the system MUST log the sink failure and continue the original chat, Agent, file, workspace, storage, or artifact operation

#### Scenario: Metrics endpoint is scraped

- **WHEN** Prometheus scrapes the configured metrics endpoint
- **THEN** the endpoint MUST return Prometheus text exposition output without requiring database, LLM, storage, or Agent runtime work

#### Scenario: Exporters are unavailable after startup

- **WHEN** the configured external collector or monitoring system becomes unavailable after backend startup
- **THEN** SmartClass user workflows MUST continue and telemetry export failures MUST be observable through local logs

### Requirement: Operational examples

The system SHALL provide local operations examples for OpenTelemetry Collector and Prometheus-compatible monitoring.

#### Scenario: Developer wants to test traces locally

- **WHEN** a developer follows the local OpenTelemetry example
- **THEN** they MUST be able to route backend OTLP telemetry to a collector or debug exporter without changing application code

#### Scenario: Developer wants to scrape metrics locally

- **WHEN** a developer follows the local Prometheus example
- **THEN** they MUST be able to scrape the backend metrics endpoint and view SmartClass metrics in a Prometheus/Grafana-compatible stack

#### Scenario: Production deployment is planned

- **WHEN** operators review the observability documentation
- **THEN** it MUST describe protecting the metrics endpoint, choosing sampling rates, avoiding secret export, and routing collector output to a backend selected by deployment configuration

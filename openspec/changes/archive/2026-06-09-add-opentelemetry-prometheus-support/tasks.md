## 1. Configuration And Dependencies

- [x] 1.1 Add optional OpenTelemetry and Prometheus Python dependencies to the backend dependency manifest.
- [x] 1.2 Add backend configuration helpers for OpenTelemetry enablement, service name, environment, OTLP endpoint/protocol, sampling ratio, and insecure TLS behavior where applicable.
- [x] 1.3 Add backend configuration helpers for Prometheus enablement, metrics path, default buckets, and metric export mode.
- [x] 1.4 Document local environment variables and safe defaults, keeping external telemetry disabled or local-only unless explicitly configured.

## 2. Observability Bootstrap

- [x] 2.1 Create an observability bootstrap module that initializes OpenTelemetry tracer/meter providers and exporters from configuration.
- [x] 2.2 Instrument the FastAPI application for HTTP request tracing without changing existing route behavior.
- [x] 2.3 Register a Prometheus metrics endpoint, defaulting to `/metrics`, only when Prometheus export is enabled.
- [x] 2.4 Ensure initialization is idempotent in tests, reloads, and repeated app construction.
- [x] 2.5 Ensure invalid explicit exporter configuration fails clearly at startup, while disabled exporters remain no-op.

## 3. Export Existing Observation Events

- [x] 3.1 Add an OpenTelemetry observation sink that exports sanitized SmartClass span/log/metric events with run correlation attributes.
- [x] 3.2 Add a Prometheus observation sink or mapper that records counters, histograms, and gauges from existing `ObservationEvent` data.
- [x] 3.3 Preserve existing `LoggingObservationSink` and optional `JsonlTraceSink` behavior.
- [x] 3.4 Update `get_observation_sink()` to compose enabled sinks from configuration without changing call sites.
- [x] 3.5 Ensure runtime sink/export failures are logged and swallowed so user workflows continue.

## 4. Metrics And Attribute Governance

- [x] 4.1 Define low-cardinality Prometheus labels for chat runs, LLM calls, tool calls, RAG retrieval, file ingestion, artifact generation, workspace execution, and storage operations.
- [x] 4.2 Explicitly prevent `run_id`, `thread_id`, `user_id`, filenames, object keys, URLs, prompt text, completion text, attachment text, and memory content from becoming Prometheus labels.
- [x] 4.3 Add OpenTelemetry attributes for correlation IDs, agent name, event name, status, error category, model, token usage, tool name, artifact type, file kind, and storage backend after sanitization.
- [x] 4.4 Normalize uncontrolled string values such as model names, routes, and tool names before export.
- [x] 4.5 Add active-run gauge updates around chat stream lifecycle if not already derivable from observation events.

## 5. Local Operations Examples

- [x] 5.1 Add an example OpenTelemetry Collector config for OTLP input and debug/Tempo-compatible trace output.
- [x] 5.2 Add an example Prometheus scrape config for the backend metrics endpoint.
- [x] 5.3 Add a minimal Grafana dashboard description or JSON covering request latency, chat run latency, LLM calls/tokens, tool failures, artifact failures, file ingestion failures, and workspace execution failures.
- [x] 5.4 Document production notes for protecting `/metrics`, avoiding secret export, and selecting trace sampling rates.

## 6. Tests And Verification

- [x] 6.1 Add tests for configuration defaults and enabled exporter configuration parsing.
- [x] 6.2 Add tests that OpenTelemetry sink receives sanitized events and includes expected SmartClass attributes.
- [x] 6.3 Add tests that Prometheus output contains expected metric names and bounded labels.
- [x] 6.4 Add tests that high-cardinality or sensitive fields are not exported as Prometheus labels.
- [x] 6.5 Add tests that exporter failures do not break `record_metric`, `trace_span`, chat stream handling, or workspace execution.
- [x] 6.6 Run the relevant backend test suite and record any tests skipped because they require a live collector or Prometheus server.

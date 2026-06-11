## Context

SmartClass already has an internal observability layer in `backend/app/core/observability.py`. It defines `RunContext`, `ObservationEvent`, `ObservationSink`, `LoggingObservationSink`, `JsonlTraceSink`, `trace_span`, `record_metric`, `log_observation`, and `observe_llm_call`. This layer sanitizes sensitive fields, truncates large payloads, categorizes errors, and is already used by Agent, graph, memory, artifact, storage, skills, and workspace execution paths.

The next step should export those existing events to platform-neutral observability systems. The implementation must not bypass current redaction, must not leak prompts, attachments, JWTs, presigned URLs, full memory contents, or host paths, and must not place high-cardinality identifiers such as `run_id`, `thread_id`, or `user_id` into Prometheus labels.

## Goals / Non-Goals

**Goals:**

- Add OpenTelemetry support for FastAPI request traces and SmartClass application spans/metrics.
- Add Prometheus-compatible metrics at a backend endpoint such as `/metrics`.
- Preserve the current `ObservationSink` API and existing JSONL/logging behavior.
- Export Agent-relevant metadata including run id, thread id, plan id, user id, agent name, event name, status, duration, error category, model name, token counts, tool name, artifact type, file kind, and storage backend where appropriate.
- Keep Prometheus label cardinality bounded and suitable for scraping.
- Make external export fully configuration-driven and disabled or harmless when dependencies/endpoints are not configured.
- Provide local collector and scrape examples without hard-coding any third-party SaaS platform into business logic.

**Non-Goals:**

- Do not add Langfuse, LangSmith, Sentry, Datadog, or vendor-specific Agent observability in this first change.
- Do not replace JSONL traces or structured logging.
- Do not introduce a full OpenTelemetry Collector deployment manager inside the application.
- Do not expose full prompts, completions, attachment text, RAG chunks, or long-term memory content to external systems by default.
- Do not change SSE event types or frontend progress/artifact contracts.

## Decisions

### Decision 1: Use the existing ObservationSink as the integration boundary

Add external exporters as sinks behind `get_observation_sink()` rather than calling OpenTelemetry or Prometheus client APIs directly from graph nodes, Agent middleware, storage code, or API handlers.

Rationale:

- The current layer already centralizes sanitization, truncation, error categorization, and run context.
- It keeps platform-specific code out of business modules.
- It allows later addition of Langfuse or other Agent platforms as another sink without changing call sites again.

Alternatives considered:

- Add OTel spans directly inside each node/tool. This gives fine control but will scatter exporter logic and duplicate redaction decisions.
- Replace internal observation events with OpenTelemetry APIs. This would break existing tests and JSONL fallback and make local debugging more dependent on external setup.

### Decision 2: Separate trace attributes from Prometheus labels

OpenTelemetry spans may include correlation attributes such as `smartclass.run_id`, `smartclass.thread_id`, `smartclass.plan_id`, and a privacy-safe user identifier. Prometheus metrics must use only bounded labels such as `event`, `status`, `error_category`, `agent_name`, `tool_name`, `model`, `artifact_type`, `file_kind`, `storage_backend`, and `route` where values are controlled or normalized.

Rationale:

- Trace backends are designed to carry per-run correlation attributes.
- Prometheus performs poorly and becomes expensive when labels contain unbounded values.
- SmartClass needs both: detailed trace lookup by run id and stable aggregate metrics for alerting.

Alternatives considered:

- Put `run_id` and `thread_id` in Prometheus labels for easy filtering. This is rejected because it creates high-cardinality time series.
- Omit correlation ids everywhere. This protects metrics but weakens trace debugging; spans/logs can safely carry sanitized ids.

### Decision 3: OpenTelemetry is optional and Collector-oriented

Configuration should support OTLP HTTP/gRPC endpoint selection, service name, environment, sample ratio, and enablement. The app exports to an OpenTelemetry Collector or compatible endpoint; it does not embed a specific backend such as Tempo, Jaeger, Grafana Cloud, Datadog, or Honeycomb.

Rationale:

- Collector-oriented export avoids vendor lock-in.
- Teams can route traces, metrics, and logs differently per environment.
- Local development can use a simple Collector + Tempo/Jaeger setup; production can use managed telemetry.

Alternatives considered:

- Export directly to Jaeger/Tempo. This is simpler for local demos but couples the app to one backend.
- Require OpenTelemetry to be enabled in all environments. This creates unnecessary startup risk for local development and tests.

### Decision 4: Prometheus endpoint is low-risk and local-first

Expose Prometheus metrics only when enabled, with a configurable path defaulting to `/metrics`. Register counters, histograms, and gauges for existing observation events and selected FastAPI/runtime metrics. The endpoint must not require authentication in local deployments by default, but deployment guidance should recommend network-level protection for production.

Rationale:

- Prometheus scraping is simple to validate and operate.
- It is the right fit for alerting on error rates, latency histograms, active runs, file ingestion failures, and artifact generation outcomes.
- Endpoint protection is deployment-specific; putting auth on Prometheus scrape endpoints often belongs at ingress/network level.

Alternatives considered:

- Push metrics to a remote gateway. Pull-based scraping is the Prometheus default and simpler for the first implementation.
- Put all metrics through OpenTelemetry only. This is viable long-term, but a direct `/metrics` endpoint is easier to run and test with the current stack.

### Decision 5: Exporter failures must never break user workflows

All external sinks must be best-effort. Exporter initialization failures caused by explicit invalid configuration may fail fast, but runtime emission failures should be logged and swallowed, matching the current `CompositeObservationSink` behavior.

Rationale:

- Observability must improve diagnosability without creating a new outage path.
- Existing behavior already isolates sink failures.

Alternatives considered:

- Treat exporter failures as request failures. This is inappropriate for telemetry paths.

## Metric And Trace Shape

Recommended Prometheus metrics:

- `smartclass_chat_runs_total{status,intent,error_category}`
- `smartclass_chat_run_duration_seconds{status,intent,error_category}`
- `smartclass_llm_calls_total{agent_name,model,status,error_category}`
- `smartclass_llm_call_duration_seconds{agent_name,model,status}`
- `smartclass_llm_tokens_total{model,token_type}`
- `smartclass_tool_calls_total{agent_name,tool_name,status,error_category}`
- `smartclass_tool_call_duration_seconds{agent_name,tool_name,status}`
- `smartclass_rag_retrievals_total{status,error_category}`
- `smartclass_rag_retrieval_duration_seconds{status}`
- `smartclass_file_ingestion_total{file_kind,status,error_category}`
- `smartclass_artifact_generation_total{artifact_type,status,error_category}`
- `smartclass_workspace_code_execution_total{language,status,error_category}`
- `smartclass_storage_operations_total{operation,backend,status,error_category}`
- `smartclass_active_runs`

Recommended OpenTelemetry attributes:

- `service.name`, `deployment.environment`
- `smartclass.run_id`, `smartclass.thread_id`, `smartclass.plan_id`
- `smartclass.user_id_hash` or internal `user_id` only when policy allows
- `smartclass.agent_name`, `smartclass.event`, `smartclass.status`
- `smartclass.error_category`, `exception.type`, sanitized `exception.message`
- `llm.model`, `llm.input_tokens`, `llm.output_tokens`, `llm.total_tokens`
- `tool.name`, `artifact.type`, `file.kind`, `storage.backend`

## Risks / Trade-offs

- OpenTelemetry packages can increase dependency surface. Mitigation: keep initialization optional and isolated in a bootstrap module.
- Prometheus labels can accidentally become high-cardinality. Mitigation: centralize label mapping and add tests that reject `run_id`, `thread_id`, `user_id`, filenames, object keys, and URLs as labels.
- Exporting LLM/Agent data can leak sensitive content. Mitigation: export only sanitized observation fields and keep prompt/completion capture out of scope for this change.
- Duplicate metrics may occur if both FastAPI instrumentation and custom events count the same thing. Mitigation: use FastAPI instrumentation for HTTP-level metrics/traces and SmartClass metrics for domain events.
- Collector or scrape endpoint deployment differs by environment. Mitigation: provide examples, not hard-coded production assumptions.

## Migration Plan

1. Add optional dependencies and configuration helpers.
2. Add an observability bootstrap module that initializes OpenTelemetry and Prometheus when enabled.
3. Instrument FastAPI during app creation or startup.
4. Add external sinks behind `get_observation_sink()`.
5. Map existing SmartClass observation events into Prometheus metrics and OpenTelemetry spans/metrics.
6. Add tests for defaults, enabled exporters, redaction, metric labels, and failure isolation.
7. Add local Collector/Prometheus/Grafana example docs.

Rollback strategy: disable `OTEL_ENABLED` and `PROMETHEUS_ENABLED` in environment configuration. Existing logging and JSONL observation paths remain available.

## Open Questions

- Should production expose `/metrics` directly from the backend container, or through an internal-only sidecar/ingress path?
- Should user identifiers be omitted, hashed, or exported as internal IDs in traces for the first deployment?
- Should OpenTelemetry metrics be enabled immediately, or should the first version use OpenTelemetry primarily for traces and Prometheus for metrics?

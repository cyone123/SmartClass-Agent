## Why

SmartClass has moved into the Agent Harness governance and engineering phase. The backend already emits internal observation events with `run_id`, `thread_id`, `plan_id`, `user_id`, `agent_name`, status, duration, and error categories, and it can write sanitized JSONL traces. That is useful for local debugging, but it is not enough for production performance monitoring, cross-run latency analysis, alerting, or external trace correlation.

The system now needs standard observability exports so operators can monitor FastAPI request health, SSE chat runs, LangGraph node latency, LLM/tool/RAG/storage behavior, file ingestion, artifact generation, and failure categories through external platforms such as OpenTelemetry collectors and Prometheus-compatible monitoring stacks.

This change adds OpenTelemetry and Prometheus support as the first external observability integration layer while preserving the existing SmartClass observability contract and privacy guardrails.

## What Changes

- Add backend configuration for OpenTelemetry and Prometheus enablement, service metadata, OTLP endpoints, sampling, metrics path, and export behavior.
- Add OpenTelemetry initialization for FastAPI request tracing and application-created spans/metrics through the existing observation sink boundary.
- Add a Prometheus metrics endpoint for low-cardinality system, Agent, file, artifact, RAG, storage, and LLM metrics.
- Extend the existing `ObservationSink` pipeline so internal SmartClass observation events can be exported externally without scattering platform-specific code across graph, agent, workspace, storage, or API modules.
- Ensure exported telemetry keeps current redaction, truncation, and secret-safety behavior and avoids high-cardinality Prometheus labels.
- Add local deployment examples for OpenTelemetry Collector and Prometheus/Grafana-compatible scraping.
- Add tests that verify exporter configuration, metric names/labels, redaction, high-cardinality label prevention, and sink failures not affecting business flow.

## Capabilities

### New Capabilities

- `external-observability`: Export SmartClass runtime observations to OpenTelemetry and Prometheus-compatible platforms while preserving run correlation, privacy protections, and existing internal observation behavior.

### Modified Capabilities

- `agent-sandbox-execution`: The existing workspace execution observability requirement remains valid; this change adds an external export path for the same sanitized execution metadata.

## Impact

- Backend configuration: `backend/app/config.py`, `.env` documentation or equivalent development notes, and dependency manifest updates.
- Backend app startup: `backend/app/main.py` or a dedicated observability bootstrap module for OpenTelemetry/FastAPI instrumentation and Prometheus route registration.
- Observability core: `backend/app/core/observability.py` gains exporter-aware sinks and metric mapping while keeping current APIs stable.
- Agent and graph flows: existing `record_metric`, `trace_span`, `observe_llm_call`, progress, artifact trace, workspace, storage, memory, and RAG observations should continue to be the source of truth.
- Tests: add or update backend tests for OpenTelemetry sink behavior, Prometheus metric output, configuration defaults, redaction, high-cardinality protection, and failure isolation.
- Operations docs: add a minimal collector and Prometheus/Grafana example for local and deployment use.

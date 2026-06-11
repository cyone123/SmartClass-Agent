# SmartClass Observability

SmartClass supports optional external observability exports while keeping the existing structured logging and JSONL trace path.

## Environment

```env
OBSERVABILITY_ENABLED=true
OBSERVABILITY_LOG_LEVEL=info
OBSERVABILITY_TRACE_JSONL_ENABLED=false

OTEL_ENABLED=false
OTEL_SERVICE_NAME=smartclass-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_TRACES_SAMPLER_ARG=1.0

PROMETHEUS_ENABLED=false
PROMETHEUS_METRICS_PATH=/metrics
PROMETHEUS_HISTOGRAM_BUCKETS=0.05,0.1,0.25,0.5,1,2.5,5,10,30,60
PROMETHEUS_EXPORT_MODE=endpoint
```

Keep external exporters disabled by default in local development unless a collector or scraper is running.

## Local Traces

Use `otel-collector.yaml` as a minimal OpenTelemetry Collector config. The backend should export OTLP HTTP traces to `http://localhost:4318/v1/traces`.

The application exports FastAPI request traces and sanitized SmartClass observation events. Trace attributes may include `smartclass.run_id`, `smartclass.thread_id`, `smartclass.plan_id`, `smartclass.agent_name`, status, duration, error category, model, token counts, tool name, artifact type, file kind, and storage backend.

## Local Metrics

Use `prometheus.yml` as a minimal scrape config. Enable `PROMETHEUS_ENABLED=true` and scrape the backend at `/metrics`.

Recommended dashboard panels:

- HTTP request rate and latency
- chat stream active runs and run duration
- LLM call count, latency, failure rate, and token totals
- tool call count, latency, and failure rate
- RAG retrieval count and latency
- artifact generation/revision success and failure counts
- file ingestion success and failure counts
- workspace code execution failures
- storage operation failures

## Production Notes

Protect `/metrics` at the network, ingress, or service-mesh layer. Do not expose it publicly.

Use trace sampling in production. Start with a low sample ratio for normal traffic and raise it temporarily during incident investigation.

Do not export full prompts, completions, attachment text, RAG chunks, long-term memory content, JWTs, Authorization headers, presigned URL signatures, object keys, or host filesystem paths. SmartClass exporters use the existing sanitization layer and keep Prometheus labels low-cardinality.

Route OpenTelemetry through a Collector rather than hard-coding a backend in application code. The Collector can forward traces to Tempo, Jaeger, Grafana Cloud, Datadog, Honeycomb, or another deployment-selected backend.

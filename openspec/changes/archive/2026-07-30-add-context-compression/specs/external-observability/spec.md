## ADDED Requirements

### Requirement: Context compression observations are emitted

The system SHALL emit sanitized observation events for context compression checks, starts, completions, skips, and failures.

#### Scenario: Compression threshold is checked

- **WHEN** the backend evaluates whether a completed chat turn needs context compression
- **THEN** it MUST emit or record a context compression check observation with bounded fields such as estimated token count, message count, threshold, and decision

#### Scenario: Compression completes

- **WHEN** context compression successfully updates a thread's messages
- **THEN** the backend MUST emit a context compression completion observation with bounded fields such as message count before and after, estimated tokens before and after, retained turn count, summary size, and duration

#### Scenario: Compression is skipped

- **WHEN** context compression is skipped because the feature is disabled, the threshold is not reached, the thread has pending approval, the thread has a resumable interrupt, or there are too few messages
- **THEN** the backend MUST record a bounded skip reason without logging raw conversation content

#### Scenario: Compression fails

- **WHEN** context compression fails
- **THEN** the backend MUST emit a failed observation with error category, error type, and sanitized error message while preserving the original chat workflow

### Requirement: Compression telemetry remains low-cardinality and redacted

The system SHALL keep context compression telemetry safe for logs, JSONL traces, OpenTelemetry, and Prometheus.

#### Scenario: Observation fields are exported

- **WHEN** context compression observations are exported to logs, JSONL, OpenTelemetry, or Prometheus
- **THEN** exported fields MUST NOT include raw prompt text, raw completion text, full chat messages, full attachment text, full RAG chunks, full memory content, JWTs, access tokens, presigned URL signatures, object keys, host paths, or filenames

#### Scenario: Prometheus labels are generated

- **WHEN** Prometheus metrics are generated from context compression observations
- **THEN** labels MUST remain bounded and MUST NOT include run id, thread id, user id, plan id, filenames, object keys, URLs, message text, or summary text

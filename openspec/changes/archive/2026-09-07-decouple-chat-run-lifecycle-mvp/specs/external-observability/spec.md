## MODIFIED Requirements

### Requirement: Prometheus metrics export

The system SHALL expose low-cardinality Prometheus metrics for SmartClass system health, Agent behavior, durable run activity, subscription activity, and long-running workflow outcomes.

#### Scenario: Agent and system observations are recorded

- **WHEN** SmartClass records observations for chat runs, SSE subscriptions, LLM calls, tool calls, RAG retrieval, file ingestion, artifact generation, workspace code execution, or storage operations
- **THEN** Prometheus metrics MUST update counters, histograms, or gauges with bounded labels suitable for aggregation and alerting

#### Scenario: Metric labels are generated

- **WHEN** Prometheus labels are generated from an observation event
- **THEN** labels MUST NOT include high-cardinality or sensitive values such as run id, thread id, user id, filenames, object keys, URLs, prompt text, completion text, attachment text, or memory content

#### Scenario: Token usage is available

- **WHEN** an LLM observation includes token usage metadata
- **THEN** Prometheus metrics MUST record input, output, and total token counts using bounded labels such as model and token type

#### Scenario: Active durable chat runs change

- **WHEN** a durable chat run starts, waits for approval, completes, fails, or is cancelled
- **THEN** Prometheus metrics MUST expose an active run gauge or equivalent metric that reflects Agent execution independently from the number of SSE subscribers

#### Scenario: Run-event subscriptions change

- **WHEN** an SSE replay subscription opens, reconnects, completes, or disconnects
- **THEN** subscription observations MUST remain distinct from durable Agent run outcome observations


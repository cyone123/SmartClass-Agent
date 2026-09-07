## ADDED Requirements

### Requirement: Redis chat-run event transport is observable

The system SHALL emit sanitized observations and low-cardinality metrics for Redis run-event publishing, live snapshot access, replay reads, blocking subscription waits, retention cleanup, and transport failures.

#### Scenario: Run event is published
- **WHEN** a run event is appended to Redis
- **THEN** the system MUST record bounded fields such as event type, status, duration, payload size, and batching outcome without recording event content or run identifiers as Prometheus labels

#### Scenario: Subscriber replays or follows events
- **WHEN** an SSE subscription reads retained events or waits for new Redis entries
- **THEN** the system MUST distinguish replayed event counts, blocking-read latency, reconnect outcome, and transport errors from Agent run outcome observations

#### Scenario: Redis event operation fails
- **WHEN** publishing, snapshot retrieval, replay, retention, or health verification fails
- **THEN** the system MUST record a sanitized error category and operation name without exporting credentials, Redis URLs, event payloads, user content, object keys, run ids, thread ids, or user ids as Prometheus labels

#### Scenario: Operators assess Redis capacity
- **WHEN** Redis event streams approach configured capacity or retention limits
- **THEN** monitoring MUST expose bounded aggregate signals for write failures, retained-event volume, active subscriptions, and detected replay gaps without scanning or exporting sensitive payloads


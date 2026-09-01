## MODIFIED Requirements

### Requirement: Thread messages are compressed after completed turns

The system SHALL evaluate a LangGraph thread for context compression after each completed user/AI turn and before the durable chat run publishes its terminal `done` event.

#### Scenario: Completed turn exceeds threshold

- **WHEN** a chat run finishes graph execution without a pending approval and the estimated effective short-term context reaches the configured compression threshold
- **THEN** the backend MUST run context compression before persisting the final `done` event

#### Scenario: Completed turn is below threshold

- **WHEN** a chat run finishes graph execution and the estimated effective short-term context is below the configured compression threshold
- **THEN** the backend MUST skip compression and complete the run without emitting a context compression progress step

### Requirement: Compression progress is visible through existing SSE progress

The system SHALL report context compression status through the existing replayable `progress` SSE event contract.

#### Scenario: Compression starts

- **WHEN** backend compression begins for a chat run
- **THEN** the backend MUST persist and emit a `progress` event containing a `context_compression` step with `running` status and a user-readable detail

#### Scenario: Compression succeeds

- **WHEN** backend compression updates the thread state successfully
- **THEN** the backend MUST persist and emit a `progress` event containing the `context_compression` step with `success` status

#### Scenario: Compression fails

- **WHEN** backend compression fails after it started
- **THEN** the backend MUST persist and emit a `progress` event containing the `context_compression` step with `failed` status and MUST continue to persist the run `done` event


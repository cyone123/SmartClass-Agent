## ADDED Requirements

### Requirement: Chat submission creates a durable run

The system SHALL persist an owned chat run before starting Agent execution and SHALL return its identifier without requiring the Agent turn to complete.

#### Scenario: User submits a message

- **WHEN** an authenticated user submits a valid message for a thread they own
- **THEN** the backend MUST create a `queued` run containing the thread, user, plan, execution input, and creation time and return the run identifier

#### Scenario: User submits an approval

- **WHEN** an authenticated user submits a valid approval for the current interrupt of a thread they own
- **THEN** the backend MUST create a new run that resumes the existing LangGraph thread without bypassing approval validation

### Requirement: Run execution is independent from event subscribers

The system SHALL keep an MVP run task alive when an SSE subscriber disconnects and SHALL stop it only on completion, explicit cancellation, or backend-process shutdown.

#### Scenario: Browser changes sessions

- **WHEN** the browser closes the current run-event subscription because another session becomes active
- **THEN** the Agent run MUST continue and persist later events without an attached subscriber

#### Scenario: Network connection is lost

- **WHEN** every subscriber for a running run disconnects unexpectedly
- **THEN** the backend MUST NOT interpret the disconnect as a run cancellation

### Requirement: Run events are ordered and replayable

The system SHALL persist each user-visible run event with a monotonically increasing sequence scoped to the run.

#### Scenario: Subscriber provides a cursor

- **WHEN** an authorized subscriber requests events after sequence `N`
- **THEN** the backend MUST emit every retained event with sequence greater than `N` in ascending order before following new events

#### Scenario: Subscriber reconnects after an event was applied

- **WHEN** a client reconnects with `Last-Event-ID` or an equivalent sequence cursor
- **THEN** the backend MUST NOT require the client to reapply events at or below that sequence

#### Scenario: Run reaches a terminal transport state

- **WHEN** execution succeeds, fails, is cancelled, or pauses for approval
- **THEN** the backend MUST persist a final `done` event containing the run identifier and final status

### Requirement: Existing chat event contracts remain usable

The system SHALL publish the existing `metadata`, `progress`, `token`, `artifact`, `artifact_trace`, `approval`, `suggestions`, `error`, and `done` event types through the replay stream.

#### Scenario: Agent emits an existing event

- **WHEN** `AgentRuntime.stream_agent_events()` yields a supported event
- **THEN** the run service MUST persist and replay the event without changing the semantic meaning of its payload

### Requirement: Run lifecycle is queryable

The system SHALL expose authorized run snapshots and active-run discovery for a conversation thread.

#### Scenario: Thread has a queued or running run

- **WHEN** the owner queries the active run for that thread
- **THEN** the backend MUST return the run id, lifecycle status, last event sequence, and current output-text snapshot

#### Scenario: Run is waiting for approval

- **WHEN** graph execution emits a pending approval
- **THEN** the run MUST transition to `waiting_approval`, persist the approval and `done` events, and no longer be returned as actively executing

### Requirement: Run access follows conversation ownership

The system SHALL authorize run creation, status access, event subscription, active-run discovery, and cancellation against the current user and owned thread.

#### Scenario: Another user requests a run

- **WHEN** an authenticated user requests status, events, or cancellation for a run owned by another user
- **THEN** the backend MUST return a not-found or forbidden response without disclosing run data

#### Scenario: Attachment identifiers are submitted

- **WHEN** a run request contains attachment identifiers
- **THEN** the backend MUST validate that every attachment belongs to the same user, plan, and thread before scheduling execution

### Requirement: Concurrent active turns are rejected

The system SHALL prevent two `queued` or `running` MVP runs from being submitted concurrently for the same thread.

#### Scenario: A thread already has an active run

- **WHEN** the owner submits another message or approval before the active run finishes
- **THEN** the backend MUST reject the new submission with a conflict response and identify the existing active run

### Requirement: Cancellation is explicit

The system SHALL distinguish subscription cancellation from an authorized request to cancel execution.

#### Scenario: Owner cancels an active run

- **WHEN** the run owner calls the cancellation endpoint for a queued or running run
- **THEN** the backend MUST request task cancellation and persist `cancelled` status with a terminal `done` event

#### Scenario: Owner cancels a terminal run

- **WHEN** the run owner calls the cancellation endpoint for a terminal or waiting-approval run
- **THEN** the backend MUST return its current state without starting another cancellation

### Requirement: Frontend reconnects per thread and run

The frontend SHALL retain run identity and the last applied event sequence per thread and SHALL reattach to an active run when that thread becomes visible again.

#### Scenario: User returns to a running session

- **WHEN** a user switches back to a thread with an active run
- **THEN** the frontend MUST fetch the active run, restore its output snapshot, and subscribe after the last applied sequence

#### Scenario: Replay contains duplicate delivery

- **WHEN** an event sequence has already been applied for the current run
- **THEN** the frontend MUST ignore that duplicate event

#### Scenario: Transient subscription failure occurs

- **WHEN** the run is still active and the event request fails without an authorization error or explicit local detach
- **THEN** the frontend MUST retry from its last sequence with bounded backoff

### Requirement: MVP restart limitation is explicit and observable

The system SHALL not silently present an orphaned in-process run as active after backend restart.

#### Scenario: Backend starts with stale queued or running MVP runs

- **WHEN** application startup finds runs that cannot have a live task in the new process
- **THEN** the backend MUST mark them failed with a sanitized restart reason and a terminal event


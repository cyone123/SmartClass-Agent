## MODIFIED Requirements

### Requirement: Run events are ordered and replayable

The system SHALL retain every user-visible event for an active or recently completed run in Redis with a monotonically increasing integer sequence scoped to that run, while PostgreSQL remains authoritative for run ownership and lifecycle status.

#### Scenario: Subscriber provides a cursor
- **WHEN** an authorized subscriber requests events after sequence `N`
- **THEN** the backend MUST emit every retained Redis event with sequence greater than `N` in ascending order before blocking for new events

#### Scenario: Subscriber reconnects after an event was applied
- **WHEN** a client reconnects with `Last-Event-ID` or an equivalent sequence cursor
- **THEN** the backend MUST NOT require the client to reapply events at or below that sequence

#### Scenario: Multiple subscribers follow one run
- **WHEN** more than one authorized subscription follows the same run
- **THEN** each subscriber MUST be able to read the complete retained sequence independently rather than compete for event delivery

#### Scenario: Run reaches a terminal transport state
- **WHEN** execution succeeds, fails, is cancelled, or pauses for approval
- **THEN** the backend MUST commit a PostgreSQL terminal snapshot with the final output and terminal sequence and MUST expose exactly one logical `done` event at that sequence through persisted Redis data or deterministic synthesis from the terminal snapshot

#### Scenario: Redis is unavailable before submission
- **WHEN** the Redis event service is unavailable while a user submits a new run
- **THEN** the backend MUST reject the submission without starting Agent execution or silently falling back to PostgreSQL event rows

#### Scenario: Redis event persistence fails during execution
- **WHEN** the backend cannot persist a required run event after bounded retries
- **THEN** the run MUST stop claiming reconnect-safe progress, record a sanitized failure in its PostgreSQL lifecycle state, and expose the recoverable terminal snapshot when Redis becomes readable

### Requirement: Run lifecycle is queryable

The system SHALL expose authorized run snapshots and active-run discovery for a conversation thread, using Redis for the live output/sequence projection and PostgreSQL for ownership and authoritative lifecycle state.

#### Scenario: Thread has a queued or running run
- **WHEN** the owner queries the active run for that thread
- **THEN** the backend MUST return the run id, PostgreSQL lifecycle status, and the latest available Redis event sequence and output-text snapshot

#### Scenario: Run has reached a terminal state
- **WHEN** the owner queries a run that succeeded, failed, was cancelled, or is waiting for approval
- **THEN** the backend MUST return its final status, output-text snapshot, and terminal event sequence from PostgreSQL without requiring retained Redis events

#### Scenario: Run is waiting for approval
- **WHEN** graph execution emits a pending approval
- **THEN** the run MUST transition to `waiting_approval`, expose the approval and terminal `done` events, and no longer be returned as actively executing

### Requirement: MVP restart limitation is explicit and observable

The system SHALL not silently present an orphaned in-process run as active after backend restart and SHALL preserve the PostgreSQL terminal snapshot as the fallback when a partial Redis stream cannot be continued.

#### Scenario: Backend starts with stale queued or running MVP runs
- **WHEN** application startup finds runs that cannot have a live task in the new process
- **THEN** the backend MUST mark them failed with a sanitized restart reason, store their final snapshot and terminal sequence in PostgreSQL, and make a logical terminal event available without restarting Agent execution

## ADDED Requirements

### Requirement: Token event batching preserves response semantics

The system SHALL coalesce adjacent token fragments into bounded event batches without changing their order or the final assistant text.

#### Scenario: Agent emits rapid token fragments
- **WHEN** multiple adjacent token fragments arrive within the configured batching window or size limit
- **THEN** the backend MUST persist them as fewer ordered token events whose concatenated text exactly matches the original fragments

#### Scenario: A state-changing event follows buffered tokens
- **WHEN** progress, artifact, trace, approval, suggestion, error, cancellation, or completion processing follows buffered token fragments
- **THEN** the backend MUST flush the buffered token text before publishing the state-changing event

### Requirement: Redis event retention has an explicit recovery boundary

The system SHALL retain active-run events for the complete supported execution window and recently completed events for a configured reconnect period, while retaining the final run snapshot in PostgreSQL beyond that period.

#### Scenario: Client reconnects inside the retention window
- **WHEN** a client reconnects with a valid cursor before the run stream expires
- **THEN** all retained events after that cursor MUST be replayed before live following resumes

#### Scenario: Client returns after terminal events expire
- **WHEN** a terminal run's Redis event data has expired
- **THEN** the backend MUST still return the final PostgreSQL output and status and MUST NOT represent the expired detailed event history as complete


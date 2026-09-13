## Purpose

Defines reliable background extraction and mutation of long-term profile and teaching-experience memories without extending the latency or failure surface of user-facing Agent execution.

## ADDED Requirements

### Requirement: Reflection does not block user-facing graph completion
The system SHALL remove profile and experience reflection from the user-facing Graph dependency chain, and memory extraction or mutation failures MUST NOT change an otherwise successful, approval-paused, failed, or cancelled chat-run outcome.

#### Scenario: Chat pauses for approval
- **WHEN** the Agent reaches an approval interrupt
- **THEN** the approval event and terminal transport event MUST become available without waiting for profile reflection to execute

#### Scenario: Artifact generation completes
- **WHEN** the Agent completes an artifact generation or revision run successfully
- **THEN** the run MUST become terminal without waiting for experience reflection to execute

#### Scenario: Background reflection fails
- **WHEN** a reflection attempt fails after the chat run has reached a user-facing boundary
- **THEN** the system MUST retain the chat-run outcome and record the reflection job as terminally failed without automatic retry

### Requirement: Eligible reflection work is durably registered
The system SHALL persist each eligible reflection request before considering its scheduling operation complete, independently of SSE subscription state and process-local tasks.

#### Scenario: New user input reaches an approval boundary
- **WHEN** a run containing new user input reaches `waiting_approval`
- **THEN** the system MUST register at most one profile-reflection job for that run, boundary, and extractor version and MUST NOT register an experience-reflection job for the incomplete teaching flow

#### Scenario: New user input completes normally
- **WHEN** a run containing new user input reaches `succeeded`
- **THEN** the system MUST register at most one applicable profile-reflection job for that run, boundary, and extractor version

#### Scenario: A teaching outcome completes successfully
- **WHEN** a succeeded run snapshot contains a completed teaching plan, generated artifact result, or artifact revision result eligible under the current experience policy
- **THEN** the system MUST register at most one experience-reflection job for that source run, business stage, and extractor version and MUST retain the outcome's evidence type

#### Scenario: Run fails or is cancelled
- **WHEN** a run reaches `failed` or `cancelled`
- **THEN** the system MUST NOT derive an experience memory from that run

#### Scenario: Subscriber disconnects
- **WHEN** all SSE subscribers disconnect before or after a run boundary
- **THEN** eligible reflection-job registration MUST remain unaffected

### Requirement: Jobs carry bounded immutable evidence
Each reflection job SHALL contain the minimum bounded source snapshot needed by its reflection policy and MUST NOT re-read mutable latest thread state as its sole evidence when it executes.

#### Scenario: Profile job is created
- **WHEN** the system registers profile reflection for a run
- **THEN** the job snapshot MUST identify the user, source run and thread, and contain the bounded new user input needed to evaluate stable profile signals

#### Scenario: Experience job is created
- **WHEN** the system registers experience reflection
- **THEN** the job snapshot MUST identify the user, source run, thread, plan, business stage, evidence type, and a bounded representation of the relevant completed outcome

#### Scenario: Thread state changes before execution
- **WHEN** later conversation turns or context compression change the current thread state before a queued job executes
- **THEN** reflection MUST use the immutable snapshot captured for that job

#### Scenario: Snapshot contains sensitive runtime data
- **WHEN** a snapshot is persisted or observed
- **THEN** it MUST exclude complete prompts, attachment bodies, RAG chunks, memory bodies unrelated to conflict checks, authorization data, signed URLs, object keys, and host paths

### Requirement: One worker processes each job at most once
The system SHALL run one designated reflection worker, SHALL atomically take pending jobs without leases, and SHALL treat processing errors or interrupted running jobs as terminal failures without automatic retry.

#### Scenario: Worker takes a pending job
- **WHEN** the designated worker selects an available pending job
- **THEN** it MUST atomically change that job from `pending` to `running` before extraction and MUST process only a job for which that transition succeeded

#### Scenario: Accidental concurrent poll occurs
- **WHEN** more than one poller attempts the same `pending` job because of deployment misconfiguration
- **THEN** the conditional state transition MUST allow no more than one poller to take that job

#### Scenario: Processing attempt fails
- **WHEN** extraction, validation, storage, or database processing fails after a job becomes `running`
- **THEN** the job MUST enter terminal `failed` with a sanitized error category and MUST NOT be automatically retried

#### Scenario: Worker process exits while processing
- **WHEN** a worker process exits after taking a job but before recording a terminal result
- **THEN** the next designated-worker startup MUST mark the leftover `running` job terminally `failed` with category `worker_interrupted` and MUST NOT execute it again

#### Scenario: Backend restarts with pending work
- **WHEN** the designated worker starts with jobs that are still `pending`
- **THEN** it MUST continue processing those jobs without requiring the originating chat run to execute again

#### Scenario: Deployment starts backend processes
- **WHEN** the backend is deployed with more than one application process
- **THEN** configuration and operational documentation MUST designate exactly one process with the reflection worker enabled

### Requirement: Automatic memory mutations are idempotent and stale-safe
The system SHALL ensure that replayed jobs do not duplicate memory effects and that stale automatic work cannot overwrite a newer manual or automatic mutation or recreate a memory protected by a later deletion.

#### Scenario: The same job is delivered twice
- **WHEN** a completed job is encountered again or its completion acknowledgement is retried
- **THEN** the resulting memory set and memory content MUST remain equivalent to a single successful execution

#### Scenario: Concurrent runs update one user's memory
- **WHEN** reflection jobs from multiple source runs target the same user memory
- **THEN** the system MUST serialize or detect conflicting mutations and MUST NOT silently replace a newer version with an older proposal

#### Scenario: User edits memory after job creation
- **WHEN** a user explicitly updates a memory after a background job captured its base version
- **THEN** that stale job MUST NOT overwrite the explicit update

#### Scenario: User deletes memory while a job is pending
- **WHEN** a user deletes a memory after a background job was registered but before its mutation is applied
- **THEN** the stale job MUST NOT recreate or update that deleted memory

#### Scenario: Completion is acknowledged after applying a mutation
- **WHEN** the memory mutation was applied but job completion has not yet been durably acknowledged
- **THEN** acknowledgement reconciliation MUST recognize the prior effect and MUST NOT apply a second mutation

### Requirement: Existing memory behavior remains compatible
The system SHALL retain account-scoped profile and experience namespaces, current online loading and retrieval behavior, privacy filtering, and the existing public memory API shapes during this phase.

#### Scenario: A new chat starts while jobs are pending
- **WHEN** online memory loading runs before queued reflection jobs complete
- **THEN** it MUST use the latest committed memories and MUST NOT wait for pending jobs

#### Scenario: User manages memory through the API
- **WHEN** a user creates, updates, or deletes memory through the existing endpoints
- **THEN** request and response shapes MUST remain compatible while the mutation participates in version and deletion protection

### Requirement: Background reflection is observable without sensitive or high-cardinality labels
The system SHALL expose job counts, processing latency, terminal outcomes, interrupted-job counts, and sanitized error categories through existing observability facilities without recording prohibited content or high-cardinality identifiers as metric labels.

#### Scenario: A job changes state
- **WHEN** a reflection job is registered, taken, succeeds, is skipped, fails during processing, or is failed as interrupted on startup
- **THEN** the system MUST emit an observation with the job kind, state, and sanitized error category where applicable

#### Scenario: Metrics are exported
- **WHEN** background-memory metrics are emitted
- **THEN** run identifiers, thread identifiers, user identifiers, filenames, object keys, URLs, snapshots, and memory contents MUST NOT appear as metric labels

### Requirement: Evaluation can await background reflection deterministically
The evaluation harness SHALL be able to wait for the reflection jobs created by a specific evaluation run to reach a terminal state before asserting memory effects, with an explicit timeout.

#### Scenario: Evaluation checks a memory write
- **WHEN** a memory evaluation case completes its Agent run and reflection jobs remain pending
- **THEN** the evaluator MUST wait only for jobs associated with that isolated source run before comparing before and after memory state

#### Scenario: Evaluation wait times out
- **WHEN** associated jobs do not reach a terminal state within the configured evaluation timeout
- **THEN** the case MUST report an error or failed assertion that distinguishes timeout from an incorrect completed mutation

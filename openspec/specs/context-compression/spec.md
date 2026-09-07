# context-compression Specification

## Purpose
TBD - created by archiving change add-context-compression. Update Purpose after archive.
## Requirements
### Requirement: Thread messages are compressed after completed turns

The system SHALL evaluate a LangGraph thread for context compression after each completed user/AI turn and before the durable chat run publishes its terminal `done` event.

#### Scenario: Completed turn exceeds threshold

- **WHEN** a chat run finishes graph execution without a pending approval and the estimated effective short-term context reaches the configured compression threshold
- **THEN** the backend MUST run context compression before persisting the final `done` event

#### Scenario: Completed turn is below threshold

- **WHEN** a chat run finishes graph execution and the estimated effective short-term context is below the configured compression threshold
- **THEN** the backend MUST skip compression and complete the run without emitting a context compression progress step

### Requirement: Compression only mutates main messages

The system SHALL compress only `TeachingAssistantState.messages` and MUST NOT mutate structured graph state fields as part of compression.

#### Scenario: Compression succeeds

- **WHEN** context compression replaces old conversation history
- **THEN** `teaching_metadata`, `rag_context`, `rag_results`, `teaching_design_plan`, `artifact_catalog`, artifact result fields, revision target fields, and revision result fields MUST remain unchanged in graph state

#### Scenario: Structured state exists

- **WHEN** structured graph state fields are present during compression
- **THEN** selected structured facts MUST be copied into the compressed context message preface without overwriting the source state fields

### Requirement: Compressed context preserves structured state preface

The system SHALL create a compressed context message that begins with a structured SmartClass state preface followed by a concise summary of older conversation messages.

#### Scenario: Teaching metadata exists

- **WHEN** `teaching_metadata` contains subject, grade, topic, objectives, duration, key points, difficult points, or completion status
- **THEN** the compressed context message MUST include a concise structured teaching metadata section near the beginning

#### Scenario: RAG context exists

- **WHEN** `rag_context` or `rag_results` are present in graph state during compression
- **THEN** the compressed context message MUST include only a bounded digest of RAG facts or citations and MUST NOT replace the original RAG state

#### Scenario: Artifacts exist

- **WHEN** artifact catalog, generation results, revision targets, or revision results are present
- **THEN** the compressed context message MUST include a bounded artifact state digest sufficient for later artifact revision routing

### Requirement: Recent raw turns are retained

The system SHALL retain a configurable number of recent raw user/AI turns after compression.

#### Scenario: Conversation has more turns than retention window

- **WHEN** compression runs on a conversation longer than the configured recent-turn retention window
- **THEN** the backend MUST replace older messages with one compressed context message and keep the configured recent raw turns

#### Scenario: Conversation has too few turns

- **WHEN** compression is requested but the conversation does not have enough older turns to compress safely
- **THEN** the backend MUST skip destructive message replacement and record the skip reason

### Requirement: Dedicated compression model is configurable

The system SHALL use a dedicated context compression model configuration boundary.

#### Scenario: Explicit compression model is configured

- **WHEN** `CONTEXT_COMPRESSION_MODEL` and its required provider settings are configured
- **THEN** the backend MUST use that model for context compression calls

#### Scenario: Compression model is unavailable

- **WHEN** compression is enabled but the compression model cannot be initialized or called
- **THEN** the backend MUST mark the compression step failed, preserve the original message state, and continue the chat stream

### Requirement: Compression is safe around approvals and interrupts

The system SHALL avoid destructive message compression while a LangGraph thread has a pending approval or resumable interrupt.

#### Scenario: Pending approval exists

- **WHEN** graph execution finishes with a pending approval payload
- **THEN** the backend MUST skip context compression for that stream

#### Scenario: Resumable interrupt exists

- **WHEN** the thread state snapshot indicates a resumable interrupt
- **THEN** the backend MUST skip destructive message compression until the interrupt has been resumed and the turn has completed

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

### Requirement: Compression is not user-visible as chat content

The system SHALL use compressed context for future model context only and MUST NOT render compressed summary content as a normal chat message.

#### Scenario: Compression message is stored

- **WHEN** a compressed context message is inserted into thread messages
- **THEN** the frontend MUST NOT display that compressed context message as a user-facing chat bubble

#### Scenario: Chat history is loaded

- **WHEN** the frontend loads chat history for a compressed thread
- **THEN** compressed context control messages MUST be hidden or filtered from normal conversation rendering

### Requirement: Compression evaluations cover long-thread regressions

The system SHALL include evaluation cases or regression tests for context compression behavior.

#### Scenario: Long teaching-design conversation is compressed

- **WHEN** an evaluation simulates a long teaching-design conversation that crosses the compression threshold
- **THEN** the compressed thread MUST preserve teaching metadata and allow subsequent graph nodes to continue the teaching-design workflow

#### Scenario: Artifact revision follows compression

- **WHEN** an evaluation asks to revise an existing artifact after compression
- **THEN** the system MUST still identify the relevant current artifact and route the revision request correctly

#### Scenario: Compression failure fallback is evaluated

- **WHEN** an evaluation or test simulates compression model failure
- **THEN** the chat run MUST complete without mutating messages destructively


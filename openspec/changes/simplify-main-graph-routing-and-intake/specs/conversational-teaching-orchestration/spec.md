## Purpose

Defines how SmartClass routes a conversation into ordinary chat, teaching design, or artifact revision and how it conversationally gathers, confirms, and carries teaching requirements into planning without unnecessary model stages.

## ADDED Requirements

### Requirement: One conversation entry produces either a reply or a workflow action
The system SHALL use one tool-capable conversation entry to decide the current turn and MUST produce exactly one of: a user-visible ordinary-chat response, a validated teaching-design start action, or a validated artifact-revision action.

#### Scenario: Ordinary conversation
- **WHEN** the user asks for ordinary conversation that does not require a teaching-design or artifact-revision workflow
- **THEN** the system MUST answer directly from the conversation entry without first invoking a separate intent-classification model call

#### Scenario: Teaching-design request
- **WHEN** the user asks to prepare a lesson, teaching design, courseware, lesson plan, or interactive teaching activity
- **THEN** the system MUST emit a validated teaching-design action and continue into teaching-requirement collection without exposing the internal action as assistant text

#### Scenario: Artifact-revision request
- **WHEN** the user asks to revise an existing artifact in the current thread
- **THEN** the system MUST emit a validated artifact-revision action carrying the request and any supported target hints into the existing artifact-revision workflow

#### Scenario: Mixed greeting and teaching request
- **WHEN** a message combines social conversation with a substantive teaching-design request
- **THEN** the system MUST prefer the teaching-design action rather than ending after a greeting response

#### Scenario: Invalid or conflicting entry result
- **WHEN** the entry produces multiple business actions, an unknown action, invalid arguments, or neither usable text nor a valid action
- **THEN** the system MUST perform a bounded repair or configured fallback and MUST NOT silently end, expose protocol data, or execute multiple workflows

### Requirement: Teaching intake uses bounded current-task conversation
The system SHALL assess teaching-requirement completeness from the bounded conversation belonging to the current teaching task and SHALL preserve an explicit task boundary independently of any partial teaching metadata.

#### Scenario: First incomplete teaching request
- **WHEN** the current teaching-task conversation lacks information needed to proceed confidently
- **THEN** the system MUST ask one concise, high-value clarification question and MUST NOT materialize a partial teaching-metadata object solely for that turn

#### Scenario: User supplies a clarification
- **WHEN** the user answers a teaching-intake clarification
- **THEN** the system MUST resume the same teaching-intake process with the initial request, prior intake questions, and current-task user clarifications available for completeness assessment

#### Scenario: Thread contains an earlier teaching task
- **WHEN** the same thread contains messages from an earlier completed or abandoned teaching task
- **THEN** the system MUST exclude that earlier task from the authoritative intake context unless the user explicitly references it

#### Scenario: Intake context approaches its budget
- **WHEN** current-task messages or attachment-derived context approach the configured intake context limit
- **THEN** the system MUST use a bounded task-scoped representation that preserves explicit teaching facts and recent corrections without repeatedly injecting full attachment bodies

#### Scenario: User cancels or changes direction during intake
- **WHEN** the user explicitly cancels teaching design or replaces it with a different request while clarification is pending
- **THEN** the system MUST leave or restart the intake scope deterministically and MUST NOT submit stale metadata for review

### Requirement: Complete teaching metadata is materialized once for review
The system SHALL materialize a canonical teaching-metadata snapshot only when the intake model submits it as complete, and SHALL validate the submission before presenting it for approval.

#### Scenario: Requirements become complete
- **WHEN** the current-task conversation contains sufficient teaching requirements
- **THEN** the intake model MUST submit one complete metadata action containing the canonical supported fields and the system MUST mark the validated snapshot complete before review

#### Scenario: Submitted metadata fails validation
- **WHEN** a metadata submission omits a required field, exceeds a field budget, contains an unsupported shape, or otherwise fails validation
- **THEN** the system MUST NOT enter metadata approval and MUST instead perform a bounded repair or ask a targeted clarification

#### Scenario: Metadata awaits approval
- **WHEN** a complete metadata snapshot passes validation
- **THEN** the system MUST pause at a durable metadata-review boundary and emit an approval payload containing the validated snapshot and the existing `metadata_review` stage

#### Scenario: User approves metadata
- **WHEN** the user submits a valid approval for the current metadata-review interrupt
- **THEN** the system MUST continue to teaching-context preparation without re-running the intake model or changing the approved metadata

#### Scenario: User requests a metadata correction
- **WHEN** the user rejects the metadata snapshot and supplies a correction
- **THEN** the system MUST resume teaching intake with the current-task conversation, the previously submitted snapshot, and the explicit correction, then require a newly validated snapshot before another approval

### Requirement: Clarification and approval remain durable and distinct
The system SHALL use durable resumable boundaries for both free-text clarification and explicit approvals, while treating only approval boundaries as approval-card states.

#### Scenario: Clarification question is emitted
- **WHEN** teaching intake asks a clarification question
- **THEN** the question MUST be stored as a visible assistant message before the workflow pauses for the next user message

#### Scenario: Clarification is pending
- **WHEN** the workflow is paused for a free-text intake reply
- **THEN** the system MUST resume directly into teaching intake on the next user message and MUST NOT emit an approval card for that pause

#### Scenario: Approval is pending
- **WHEN** metadata review or teaching-plan review is pending
- **THEN** the system MUST expose the current interrupt identifier and stage through the existing approval contract and MUST reject stale approval identifiers

#### Scenario: Workflow resumes after an interrupt
- **WHEN** a clarification or approval interrupt resumes
- **THEN** model work completed before that interrupt MUST NOT be repeated merely because of interrupt replay

### Requirement: Existing SSE and frontend contracts remain compatible
The system SHALL represent the simplified workflow through the existing replayable SSE event vocabulary and SHALL preserve the payloads used by progress, text, and approval UI cards.

#### Scenario: Ordinary response streams
- **WHEN** the conversation entry returns an ordinary response
- **THEN** user-visible text MUST stream through `token` events and the run MUST finish through the existing `done` event without exposing tool-call arguments

#### Scenario: Intake asks a question
- **WHEN** teaching intake determines that requirements are incomplete
- **THEN** the progress state MUST identify the intake work, the question MUST be delivered as user-visible assistant text, and no empty assistant bubble or approval card may be produced

#### Scenario: Metadata review begins
- **WHEN** validated metadata reaches the metadata-review interrupt
- **THEN** the system MUST emit an `approval` event whose `stage` is `metadata_review` and whose metadata remains renderable by the existing structured approval card

#### Scenario: Teaching-plan review begins
- **WHEN** teaching planning finishes and awaits artifact selection
- **THEN** the existing `teaching_plan_review` approval payload and artifact options MUST remain compatible with the frontend

#### Scenario: Client reconnects
- **WHEN** an SSE client reconnects to a run that streamed text or paused for approval
- **THEN** event ordering, sequence identifiers, terminal status, and persisted approval payloads MUST remain replayable through the durable run stream

### Requirement: Memory follows session, turn, and teaching-task boundaries
The system SHALL preserve the established separation between session Profile context, turn-scoped ordinary-chat Experience, and the task-scoped Experience snapshot used after teaching metadata approval.

#### Scenario: Conversation entry or teaching intake invokes a model
- **WHEN** the entry or intake model runs in an authenticated session
- **THEN** it MUST receive the bounded session Profile snapshot without another Profile Store query

#### Scenario: Profile contains historical teaching facts
- **WHEN** Profile memory describes a previous subject, grade, topic, duration, or preference
- **THEN** teaching intake MUST treat it as untrusted background and MUST NOT use it to fill a missing current-task fact

#### Scenario: Ordinary chat benefits from Experience
- **WHEN** an ordinary teaching-related discussion requires reusable Experience memory
- **THEN** the entry process MAY perform one bounded read-only Experience lookup before answering, and that result MUST remain turn-scoped rather than becoming a teaching-task snapshot

#### Scenario: Metadata has not been approved
- **WHEN** teaching intake or metadata review is still pending
- **THEN** the system MUST NOT establish the downstream teaching-task Experience snapshot

#### Scenario: Metadata is approved
- **WHEN** approved metadata makes the teaching task sufficiently defined
- **THEN** the system MUST resolve or reuse one bounded Experience snapshot from the initial request, current-task clarifications, and approved metadata and MUST make it available to teaching planning

#### Scenario: Approved context proceeds to artifacts
- **WHEN** teaching planning, approval resume, and artifact generation operate on the unchanged task scope
- **THEN** they MUST reuse the same Experience snapshot without separate automatic retrieval in each artifact branch

#### Scenario: Approved task scope changes materially
- **WHEN** an approved correction changes retrieval-significant teaching facts
- **THEN** the system MUST invalidate the old scope key and resolve exactly one refreshed Experience snapshot for downstream consumers

### Requirement: Teaching context is prepared after approval
The system SHALL prepare knowledge-base context and reusable teaching Experience only after metadata approval and SHALL make both results available before teaching planning begins.

#### Scenario: Independent context sources are available
- **WHEN** approved metadata can be used for both knowledge retrieval and Experience resolution
- **THEN** the system MUST obtain the independent bounded contexts concurrently when both sources are enabled and MUST preserve their distinct provenance and failure state

#### Scenario: Optional context source fails
- **WHEN** RAG or non-required Experience retrieval fails under its documented fail-open policy
- **THEN** the workflow MUST record a sanitized degraded outcome and continue when teaching planning remains safe without that source

### Requirement: Simplified orchestration remains safely observable and evaluable
The system SHALL observe business stages independently of implementation node names and SHALL provide evaluation evidence for routing, intake, approval, streaming, memory, and latency behavior.

#### Scenario: A business stage runs
- **WHEN** entry routing, intake, clarification, metadata review, context preparation, or teaching planning changes state
- **THEN** progress and observations MUST use stable low-cardinality stage identifiers without recording prompt text, metadata bodies, memory bodies, attachment content, user identifiers, object keys, URLs, or host paths as metric labels

#### Scenario: Simplified workflow is evaluated
- **WHEN** the change is tested against ordinary chat, mixed intent, artifact revision, incomplete intake, complete intake, corrections, stale approvals, reconnects, and memory cases
- **THEN** the evaluation MUST assert final actions and observable graph state rather than depending on removed internal node functions

#### Scenario: Model-call efficiency is compared
- **WHEN** pre-change and post-change workflow evidence is collected
- **THEN** it MUST report model-call count and latency separately for ordinary chat, first incomplete teaching requests, clarification turns, complete teaching requests, and memory-assisted chat

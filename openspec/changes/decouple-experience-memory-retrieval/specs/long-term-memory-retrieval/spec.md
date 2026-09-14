## Purpose

Defines how long-term Profile memory is established as stable session context and how relevant Experience memory is semantically retrieved, bounded, shared across a teaching-task workflow, and safely supplied to model and artifact Agent calls.

## ADDED Requirements

### Requirement: Profile memory is initialized once as bounded session context
The system SHALL load the authenticated user's committed Profile memories when a new conversation session begins, SHALL render the available Profile set in a deterministic order, and SHALL apply a configured context-length limit without relevance selection.

#### Scenario: New session has Profile memories
- **WHEN** a new conversation session begins for an authenticated user with committed Profile memories
- **THEN** the system MUST load that user's Profile namespace, render the memories as one bounded Profile context, and make that context available before intent recognition

#### Scenario: Profile context exceeds its limit
- **WHEN** the rendered Profile context exceeds the configured Profile context limit
- **THEN** the system MUST deterministically truncate it and record truncation without invoking a selector model

#### Scenario: Session resumes after an interrupt
- **WHEN** an existing conversation session resumes from a persisted approval or clarification interrupt
- **THEN** the system MUST reuse the established Profile context and MUST NOT retrieve or reselect Profile memory again

#### Scenario: Later session starts after Profile changes
- **WHEN** a later new session begins after committed Profile memories changed
- **THEN** the new session MUST load the latest committed Profile set while the earlier session continues using its snapshot

### Requirement: Applicable business calls reuse the same session Profile context
The system SHALL supply the bounded Profile snapshot to applicable user-facing business model and artifact Agent calls without another Profile Store query, purpose-specific filtering, or a separate Profile cache.

#### Scenario: Multiple business calls run in one session
- **WHEN** intent recognition, metadata extraction, follow-up, teaching design, artifact generation, or artifact revision runs within one session
- **THEN** each applicable call MUST receive the same established Profile context without another Profile Store query

#### Scenario: Current input conflicts with Profile memory
- **WHEN** the user's current explicit instruction conflicts with Profile memory
- **THEN** the supplied context MUST state that the current explicit instruction takes precedence

#### Scenario: Internal memory operation runs
- **WHEN** an Experience selector or memory-reflection model runs internally
- **THEN** the system MUST NOT recursively inject Profile or Experience context into that operation

### Requirement: Experience queries represent the bounded teaching task
The system SHALL represent an Experience retrieval need as a trusted, bounded request whose query combines the task's stable intent with relevant recent changes rather than using only the latest user message.

#### Scenario: Multi-turn teaching request is clarified
- **WHEN** a user supplies a teaching request and later clarifies it over multiple turns
- **THEN** the Experience query MUST include a bounded representation of the initial request, recent relevant user clarifications, and confirmed teaching metadata

#### Scenario: Artifact generation uses teaching context
- **WHEN** Experience is needed for artifact generation
- **THEN** the query MUST include the shared teaching-task summary and MAY identify the task or artifact scope without discarding the common teaching intent

#### Scenario: Artifact revision changes scope
- **WHEN** a revision request materially changes the teaching topic, audience, objectives, or reusable experience needed
- **THEN** the system MUST construct one refreshed bounded task query from the revised scope

#### Scenario: Query source contains excessive or sensitive context
- **WHEN** messages, metadata, plans, or revision input contain excessive or unrelated context
- **THEN** the system MUST bound and sanitize query material and MUST NOT include attachments, authorization data, checkpoint internals, or another user's identity

### Requirement: Experience semantic search is explicitly enabled and verifiable
The system SHALL use configured semantic indexing for Experience memories, SHALL keep Profile memories outside that semantic index, and SHALL fail visibly at configuration or verification boundaries instead of silently claiming semantic retrieval while returning recency-only results.

#### Scenario: Experience memory is committed
- **WHEN** a new or updated Experience memory is committed
- **THEN** its configured descriptive fields MUST be eligible for semantic indexing under the authenticated user's Experience namespace

#### Scenario: Profile memory is committed
- **WHEN** a Profile memory is committed
- **THEN** it MUST remain excluded from Experience semantic indexing

#### Scenario: Semantic query is executed
- **WHEN** the system searches Experience memory with a task query
- **THEN** returned semantic candidates MUST retain their relevance ordering and available similarity metadata through candidate selection

#### Scenario: Semantic search is expected but unavailable
- **WHEN** Experience semantic retrieval is enabled but the Store lacks compatible index configuration or embeddings
- **THEN** startup or an explicit health/verification check MUST report the misconfiguration and retrieval MUST use the documented fail-open behavior without labeling recency results as semantic matches

#### Scenario: Existing Experience memories predate semantic indexing
- **WHEN** semantic indexing is enabled for a deployment containing existing Experience memories
- **THEN** an idempotent backfill process MUST make those memories searchable without changing their public content or ownership

### Requirement: Experience provider returns a bounded relevant bundle
The system SHALL search only the authenticated user's Experience namespace, combine deterministic exact matching with semantic candidates, invoke a selector model only when the bounded candidate set remains ambiguous, and return a bounded structured result.

#### Scenario: Exact title match exists
- **WHEN** the task query explicitly contains the title of an available Experience memory
- **THEN** the provider MUST select that memory without invoking the selector model

#### Scenario: Semantic candidates have sufficient confidence
- **WHEN** semantic search returns valid high-confidence candidates within the request limits
- **THEN** the provider MUST preserve relevance order and MAY skip selector-model reranking

#### Scenario: Candidate relevance remains ambiguous
- **WHEN** exact matching and semantic scores do not provide sufficient confidence
- **THEN** the provider MUST allow the selector model to choose no more than the request item limit from bounded valid candidate summaries

#### Scenario: Selector returns invalid identifiers
- **WHEN** selector output contains unknown, duplicate, or excessive identifiers
- **THEN** the provider MUST discard invalid values and enforce the request item limit before loading content

#### Scenario: Selected content exceeds its budget
- **WHEN** selected Experience content exceeds the configured context limit
- **THEN** the provider MUST deterministically truncate or omit content, remain within the limit, and indicate truncation

#### Scenario: Retrieval fails
- **WHEN** Store access, embedding search, selection, or content loading fails for a non-required request
- **THEN** the provider MUST return an empty degraded result, record a sanitized failure observation, and allow business execution to continue

### Requirement: A teaching workflow shares one bounded Experience snapshot
The system SHALL resolve one bounded Experience snapshot for an unchanged teaching-task scope and SHALL reuse it across teaching design, approval/resume, and all artifact-generation branches instead of resolving similar requests independently.

#### Scenario: Teaching metadata is confirmed
- **WHEN** confirmed metadata makes the teaching task sufficiently defined and teaching design consumes Experience
- **THEN** the system MUST resolve one Experience snapshot and associate it with a deterministic task-scope key

#### Scenario: Teaching plan is approved and artifacts fan out
- **WHEN** PPT, DOCX, and HTML artifact branches start for the unchanged teaching task
- **THEN** every branch MUST reuse the same bounded Experience snapshot without another automatic Store search or selector call

#### Scenario: Workflow resumes after approval
- **WHEN** the teaching workflow resumes after an interrupt with the same task-scope key
- **THEN** it MUST reuse the persisted bounded snapshot instead of resolving Experience again

#### Scenario: Teaching task scope changes materially
- **WHEN** confirmed metadata or revision intent changes the task-scope key
- **THEN** the workflow MUST resolve exactly one refreshed snapshot and share it across all downstream branches for that scope

#### Scenario: Normal chat requests Experience
- **WHEN** an eligible teaching-related normal-chat turn requests Experience outside a teaching workflow
- **THEN** retrieval MUST remain scoped to that turn and MUST NOT become an implicit snapshot for unrelated later turns

### Requirement: Model invocation accepts resolved task memory consistently
The system SHALL provide a common invocation boundary for ordinary, structured-output fallback, and streaming model calls that can receive an already resolved Experience bundle and compose it with the session Profile context in a stable order.

#### Scenario: Teaching design receives a resolved bundle
- **WHEN** teaching design resolves or reuses the task Experience snapshot
- **THEN** the invocation boundary MUST inject the same bounded bundle as delimited background data before invoking the model

#### Scenario: Structured primary model falls back
- **WHEN** a structured primary model fails after a bundle has been resolved
- **THEN** the fallback MUST receive the identical Profile and Experience context without another retrieval

#### Scenario: Streaming begins
- **WHEN** a streaming model call needs Experience
- **THEN** retrieval MUST finish before streaming starts and no automatic retrieval may occur after streaming begins

#### Scenario: Memory content contains instructions
- **WHEN** Profile or Experience content contains instruction-like text
- **THEN** it MUST be identified as untrusted historical background that cannot override system rules or the user's current explicit instruction

### Requirement: Artifact Agents receive a pre-rendered task system prompt
For each artifact task, the system SHALL render the complete task-specific system prompt once from static Agent instructions, the session Profile snapshot, and the shared Experience snapshot, then SHALL make that same prompt available to every stateless model round without performing automatic memory retrieval inside the model-call hook.

#### Scenario: Artifact task starts
- **WHEN** a generation or revision artifact task begins
- **THEN** the system MUST render one bounded complete system prompt and pass it through trusted per-run context to the reusable Agent runnable

#### Scenario: Agent performs multiple tool rounds
- **WHEN** an artifact Agent performs multiple model/tool rounds
- **THEN** every model request MUST receive the same pre-rendered system prompt while the dynamic prompt integration performs no Store query, selector call, request fingerprinting, or memory-cache lookup

#### Scenario: Parallel artifact branches execute
- **WHEN** PPT, DOCX, and HTML branches execute concurrently
- **THEN** each branch MUST receive its own artifact instructions plus the same shared Profile and Experience snapshots without cross-task or cross-user leakage

#### Scenario: Eligible Agent needs additional experience
- **WHEN** an eligible artifact Agent explicitly searches for Experience not covered by the shared snapshot
- **THEN** the read-only search MUST use authenticated runtime identity, the bounded provider, and a genuinely new bounded query without accepting caller-supplied identity or write arguments

### Requirement: Retrieval freshness follows explicit session, task, and turn boundaries
The system SHALL keep Profile stable for a conversation session, Experience stable for an unchanged teaching-task scope, and normal-chat Experience scoped to an eligible turn, and SHALL not wait for pending reflection jobs before reading committed memories.

#### Scenario: Reflection jobs are pending
- **WHEN** Profile or Experience reflection jobs remain pending during initialization or retrieval
- **THEN** retrieval MUST use the latest committed memories and MUST NOT wait for those jobs

#### Scenario: Experience memory changes during an unchanged teaching workflow
- **WHEN** Experience memories change after the workflow established its task snapshot
- **THEN** the active unchanged workflow MUST continue using its bounded snapshot until an explicit scope refresh boundary occurs

### Requirement: Retrieval is observable without exposing memory content
The system SHALL observe Profile initialization, Experience semantic resolution, task-snapshot reuse/refresh, and explicit Agent searches using bounded low-cardinality metadata and MUST NOT record memory bodies, query bodies, prompts, user identifiers, run identifiers, object keys, URLs, or host paths as metric labels.

#### Scenario: Profile initialization completes
- **WHEN** Profile initialization succeeds, is empty, truncates, or fails open
- **THEN** the system MUST record a sanitized outcome, item count, truncation state, and duration without Profile content

#### Scenario: Experience snapshot resolves or is reused
- **WHEN** Experience retrieval resolves, reuses a task snapshot, truncates, returns empty, or degrades
- **THEN** the system MUST record purpose, strategy, candidate count, selected count, truncation, reuse/refresh, degradation, and duration using approved low-cardinality dimensions

#### Scenario: Semantic retrieval is unavailable
- **WHEN** retrieval degrades because semantic indexing is unavailable
- **THEN** observations MUST distinguish that degradation from a successful semantic match without exposing queries or memory content

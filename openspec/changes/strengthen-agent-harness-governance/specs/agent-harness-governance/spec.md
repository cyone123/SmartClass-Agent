## ADDED Requirements

### Requirement: Agent roles are explicitly modeled

The system SHALL define stable Agent role identifiers for SmartClass Agent responsibilities, including main-flow, attachment-analysis, artifact-generation, artifact-modification, memory-reflection, and evaluation roles.

#### Scenario: Agent run starts with a known role

- **WHEN** an Agent run or graph node invokes governed Agent behavior
- **THEN** the system MUST associate the operation with a known Agent role and include that role in policy and audit evaluation

#### Scenario: Unknown role attempts governed tool use

- **WHEN** an unknown Agent role attempts to call a governed tool
- **THEN** the system MUST deny the call or classify it as a policy failure before performing the tool action

### Requirement: Tool permission tiers are centrally defined

The system SHALL classify governed Agent tools with centrally defined permission tiers, including read-only, workspace-write, code-execution, object-storage-write, memory-read, memory-write, and external-network tiers.

#### Scenario: Governed tool is registered

- **WHEN** a sensitive Agent tool is made available to an Agent
- **THEN** the tool MUST have permission tier metadata, allowed Agent roles, and required runtime context declared in the governance contract

#### Scenario: Tool lacks required context

- **WHEN** a governed tool call is missing required runtime context such as `run_id`, `user_id`, `plan_id`, `thread_id`, or `artifact_id`
- **THEN** the system MUST reject the call or emit a policy failure without performing the protected action

### Requirement: High-risk Agent actions are policy controlled

The system SHALL route high-risk Agent actions through an explicit policy decision before execution.

#### Scenario: Existing artifact would be overwritten

- **WHEN** an Agent action would overwrite or replace an existing user-visible artifact
- **THEN** the system MUST require an explicit allow decision or use the existing revision flow instead of silently overwriting the artifact

#### Scenario: External network access is requested

- **WHEN** an Agent tool requests external network access
- **THEN** the system MUST deny the action unless the tool tier, Agent role, configuration, and approval policy explicitly allow it

#### Scenario: Long-running or batch work is requested

- **WHEN** an Agent action is classified as batch or long-running work
- **THEN** the system MUST record the policy decision and expose progress or failure through the existing run status, progress, artifact, or error contracts

### Requirement: Agent audit records are structured and sanitized

The system SHALL emit structured audit records for governed Agent and tool actions with correlation fields, summaries, duration, status, and error category while avoiding sensitive content.

#### Scenario: Governed tool succeeds

- **WHEN** a governed tool call completes successfully
- **THEN** the system MUST emit an audit record containing `run_id`, `thread_id` when available, `plan_id` when available, `user_id`, `agent_name`, `tool_name`, permission tier, input summary, output summary, duration, and success status

#### Scenario: Governed tool fails

- **WHEN** a governed tool call fails
- **THEN** the system MUST emit an audit record containing the same correlation fields, failed status, standardized error category, and sanitized failure summary

#### Scenario: Sensitive content is present

- **WHEN** tool input, tool output, prompts, attachment text, memory content, object keys, URLs, JWTs, passwords, or host paths are present
- **THEN** the audit record MUST omit, redact, or truncate those values before logging, tracing, returning to the Agent, or sending SSE events

### Requirement: Agent failures use standardized categories

The system SHALL classify Agent runtime failures with a shared taxonomy covering model, tool, permission, user-input, file-processing, storage, memory, RAG, artifact, timeout, external-service, and unknown failures.

#### Scenario: Permission failure occurs

- **WHEN** a tool call violates Agent role, permission tier, ownership, workspace, or approval policy
- **THEN** the system MUST classify the failure as a permission failure and return a user-readable summary without exposing internal stack traces

#### Scenario: User input is insufficient

- **WHEN** an Agent cannot continue because required teaching, artifact, or modification target information is missing
- **THEN** the system MUST classify the condition as user-input related and preserve existing approval or clarification behavior

#### Scenario: Artifact generation fails

- **WHEN** artifact generation or modification fails due to a tool, storage, timeout, model, or file-processing problem
- **THEN** the system MUST mark the artifact failed with a user-readable summary and record the standardized error category internally

### Requirement: Governance preserves user ownership and file-chain boundaries

The system SHALL enforce backend user ownership and the correct knowledge, attachment, or artifact file chain for Agent actions.

#### Scenario: Agent reads a user resource

- **WHEN** an Agent action reads or uses a plan, thread, knowledge file, attachment file, memory item, or artifact file
- **THEN** the system MUST validate the resource against the current backend `user_id` and relevant business context before using it

#### Scenario: Agent writes a generated file

- **WHEN** an Agent creates or modifies a user-visible file
- **THEN** the output MUST enter the artifact file chain through `StorageService` and artifact service behavior rather than remaining only in a temporary workspace

#### Scenario: Attachment is used as context

- **WHEN** an Agent uses an uploaded conversational attachment
- **THEN** the system MUST treat it as an attachment chain resource and MUST NOT mix it with knowledge-file or artifact-file storage semantics

### Requirement: Governance evaluations are repeatable

The system SHALL provide repeatable backend evaluation cases for Agent governance behavior.

#### Scenario: Evaluation fixture is executed

- **WHEN** a governance evaluation fixture runs
- **THEN** it MUST specify input, context, expected route or Agent role, expected memory behavior when applicable, expected tool permission behavior, key assertions, and allowed fuzzy matching rules

#### Scenario: Unsafe behavior is evaluated

- **WHEN** an evaluation case covers unauthorized files, dangerous commands, external network requests, sensitive memory writes, or cross-user resources
- **THEN** the system MUST assert that the behavior is denied, classified, audited, and surfaced through a safe user-readable failure path

#### Scenario: Model output is nondeterministic

- **WHEN** an evaluation depends on model-generated text
- **THEN** the test MUST use structured assertions, deterministic fakes, or a rubric helper rather than relying only on full-string snapshots

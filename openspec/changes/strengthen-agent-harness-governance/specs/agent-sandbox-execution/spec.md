## MODIFIED Requirements

### Requirement: Observability and audit metadata

The system SHALL record enough metadata to debug, govern, and audit local or Daytona-backed workspace execution without leaking sensitive content.

#### Scenario: Execution is logged

- **WHEN** a workspace execution is attempted
- **THEN** logs or observation records MUST include run id, thread id, plan id when available, user id, agent name when available, sandbox id or name when applicable, backend type, language, entrypoint summary, duration, status, governance permission tier, and standardized error category when failed

#### Scenario: Governance audit record is emitted

- **WHEN** `run_workspace_code`, `list_workspace_files`, `read_workspace_file`, `write_workspace_file`, or `replace_workspace_text` is called by an Agent
- **THEN** the system MUST emit a sanitized governance audit record for the workspace tool call using the shared Agent audit contract

#### Scenario: Output is large

- **WHEN** stdout, stderr, file content, or trace content exceeds configured limits
- **THEN** the system MUST truncate it before returning to the agent, sending SSE events, writing audit records, or writing logs

#### Scenario: Secrets are present in configuration

- **WHEN** Daytona credentials or other service credentials are configured
- **THEN** the system MUST NOT include full secret values in logs, audit records, trace entries, progress details, or agent-visible output

#### Scenario: Workspace failure occurs

- **WHEN** workspace execution, file synchronization, path validation, dependency-install detection, sandbox creation, sandbox cleanup, or output collection fails
- **THEN** the system MUST classify the failure with the shared Agent governance error taxonomy and expose only a user-readable summary to the frontend or Agent response

## ADDED Requirements

### Requirement: Workspace tools participate in governance policy

The system SHALL enforce shared Agent governance policy for workspace read, write, text replacement, and code execution tools.

#### Scenario: Agent role is not allowed to execute code

- **WHEN** an Agent role without code-execution permission calls `run_workspace_code`
- **THEN** the system MUST reject the call before running local code or creating a Daytona sandbox command

#### Scenario: Workspace write lacks required context

- **WHEN** a workspace write or text replacement call lacks required run, thread, user, or workspace context
- **THEN** the system MUST reject the call and record a permission or context failure through the governance audit contract

#### Scenario: Workspace read is allowed

- **WHEN** an allowed Agent role reads a valid workspace-relative UTF-8 file inside the current run workspace
- **THEN** the system MUST preserve the existing response shape while also recording the governed read action

### Requirement: Workspace safety is covered by evaluations

The system SHALL include repeatable evaluation or regression cases for workspace governance safety.

#### Scenario: Path traversal evaluation runs

- **WHEN** an evaluation case attempts absolute paths, traversal paths, or paths outside the current run workspace
- **THEN** the system MUST assert that the operation is rejected before local or remote execution and that a standardized permission failure is audited

#### Scenario: Dependency installation evaluation runs

- **WHEN** an evaluation case attempts blocked Python, Node, npm, or pip dependency installation through workspace code execution
- **THEN** the system MUST assert that execution is rejected before process or sandbox execution begins

#### Scenario: Workspace output evaluation runs

- **WHEN** an evaluation case generates files in the workspace output directory
- **THEN** the system MUST assert that returned output paths are workspace-relative, do not expose host absolute paths, and can enter the artifact flow when promoted

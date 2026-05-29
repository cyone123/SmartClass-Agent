# agent-sandbox-execution Specification

## Purpose
TBD - created by archiving change introduce-daytona-agent-sandbox. Update Purpose after archive.
## Requirements
### Requirement: Configurable workspace execution backend

The system SHALL allow backend configuration to choose between the existing local workspace execution backend and a Daytona sandbox execution backend.

#### Scenario: Local backend remains the default

- **WHEN** no Daytona execution backend is enabled in configuration
- **THEN** workspace code execution MUST continue to use the existing local backend behavior

#### Scenario: Daytona backend is selected

- **WHEN** configuration selects the Daytona execution backend and required Daytona settings are present
- **THEN** `run_workspace_code` MUST execute supported workspace code through a Daytona sandbox

#### Scenario: Daytona configuration is incomplete

- **WHEN** configuration selects the Daytona backend but required credentials, API URL, target, snapshot, or image settings are missing
- **THEN** the system MUST fail startup or backend initialization with a clear configuration error

### Requirement: Workspace tool contract preservation

The system SHALL preserve the existing workspace tool interface exposed to agents while changing the code execution environment.

#### Scenario: Agent runs code through existing tool

- **WHEN** an agent calls `run_workspace_code` with a supported language and entrypoint
- **THEN** the tool MUST return a JSON payload compatible with the existing `WorkspaceExecutionResult` fields

#### Scenario: Agent reads and writes workspace files

- **WHEN** an agent calls `list_workspace_files`, `read_workspace_file`, `write_workspace_file`, or `replace_workspace_text`
- **THEN** those tools MUST keep their existing path validation, UTF-8 text behavior, and JSON response shape

#### Scenario: Unsupported language requested

- **WHEN** an agent requests a workspace language that is not allowed by SmartClass
- **THEN** the system MUST reject the request before creating or executing a Daytona sandbox command

### Requirement: Daytona sandbox lifecycle management

The system SHALL create or obtain a Daytona sandbox with SmartClass run metadata before remote execution and apply lifecycle cleanup after execution.

#### Scenario: Sandbox is created for a run

- **WHEN** Daytona execution begins for a workspace run
- **THEN** the sandbox MUST be labeled with SmartClass correlation fields including run id, thread id, plan id when available, and agent name when available

#### Scenario: Execution completes

- **WHEN** remote execution finishes successfully or unsuccessfully
- **THEN** the system MUST apply the configured sandbox cleanup policy, such as stop, delete, or rely on auto-stop/auto-delete

#### Scenario: Cleanup fails

- **WHEN** sandbox cleanup fails after execution
- **THEN** the system MUST log the sandbox identity and cleanup failure without masking the original execution result

### Requirement: Remote file synchronization and output collection

The system SHALL synchronize the local workspace files needed for execution into Daytona and collect generated outputs back into the local SmartClass artifact flow.

#### Scenario: Remote execution starts

- **WHEN** Daytona execution starts
- **THEN** the system MUST upload the current local workspace files required by the entrypoint into the sandbox work directory

#### Scenario: Code writes output files

- **WHEN** sandbox code writes files to the configured output directory
- **THEN** the system MUST download those files back into the local run output directory before returning execution results

#### Scenario: Output files are reported

- **WHEN** execution returns to the agent
- **THEN** `output_files` MUST list changed or generated files using SmartClass workspace-relative POSIX paths

### Requirement: Sandbox execution environment variables

The system SHALL provide SmartClass workspace environment variables inside the Daytona sandbox using remote sandbox paths.

#### Scenario: Code reads workspace environment

- **WHEN** code runs inside Daytona
- **THEN** `AGENT_WORKSPACE_ROOT`, `AGENT_RUN_ROOT`, and `AGENT_OUTPUT_DIR` MUST point to valid paths inside the sandbox

#### Scenario: Remote paths are exposed

- **WHEN** execution output includes workspace metadata
- **THEN** the metadata MUST avoid exposing host-specific Windows absolute paths to sandbox code

### Requirement: Security policy continuity

The system SHALL continue enforcing SmartClass workspace security policies when using Daytona.

#### Scenario: Path traversal attempted

- **WHEN** an agent supplies an absolute path or traversal path for a workspace operation
- **THEN** the system MUST reject the operation before remote file upload or execution

#### Scenario: Dependency installation command detected

- **WHEN** the entrypoint source contains blocked dependency installation commands
- **THEN** the system MUST reject execution before creating or running the Daytona process

#### Scenario: Network policy configured

- **WHEN** Daytona sandbox network controls are configured
- **THEN** the system MUST apply those controls during sandbox creation or before code execution

### Requirement: Execution limits and failure reporting

The system SHALL apply execution limits and map Daytona failures into SmartClass-visible result and error categories.

#### Scenario: Remote command succeeds

- **WHEN** Daytona execution exits with code zero within the timeout
- **THEN** the system MUST return `exit_code` zero, `timed_out` false, truncated stdout and stderr, and collected output files

#### Scenario: Remote command fails

- **WHEN** Daytona execution exits with a nonzero code
- **THEN** the system MUST return the nonzero `exit_code`, truncated stdout and stderr, and mark progress as failed

#### Scenario: Remote command times out

- **WHEN** Daytona execution exceeds the configured timeout
- **THEN** the system MUST return or raise a timeout-classified failure with `timed_out` true when an execution result is available

#### Scenario: Daytona service error occurs

- **WHEN** sandbox creation, file synchronization, command execution, or output collection fails due to Daytona API or service errors
- **THEN** the system MUST expose a user-readable error summary and log structured internal details with SmartClass correlation ids

### Requirement: Observability and audit metadata

The system SHALL record enough metadata to debug and audit Daytona-backed workspace execution without leaking sensitive content.

#### Scenario: Execution is logged

- **WHEN** a Daytona-backed execution is attempted
- **THEN** logs MUST include run id, thread id, plan id when available, sandbox id or name, backend type, language, entrypoint, duration, status, and error category when failed

#### Scenario: Output is large

- **WHEN** stdout, stderr, or trace content exceeds configured limits
- **THEN** the system MUST truncate it before returning to the agent, sending SSE events, or writing logs

#### Scenario: Secrets are present in configuration

- **WHEN** Daytona credentials or other service credentials are configured
- **THEN** the system MUST NOT include full secret values in logs, trace entries, progress details, or agent-visible output


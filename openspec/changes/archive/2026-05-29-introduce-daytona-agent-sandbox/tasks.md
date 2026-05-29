## 1. Configuration And Dependency Setup

- [x] 1.1 Add the Daytona Python SDK dependency to the backend dependency manifest used by the project.
- [x] 1.2 Add backend configuration fields for workspace execution backend selection, Daytona API key, API URL, target, snapshot or image, lifecycle defaults, network policy, and Daytona execution timeout.
- [x] 1.3 Validate Daytona configuration during backend initialization when the Daytona backend is selected, while keeping the local backend as the default.
- [x] 1.4 Document the required Daytona environment variables in the backend configuration example or developer notes without committing secrets.

## 2. Execution Backend Integration

- [x] 2.1 Add a `DaytonaExecutionBackend` implementation behind the existing `ExecutionBackend` interface in `backend/app/core/workspace.py` or a focused companion module.
- [x] 2.2 Update `WorkspaceManager` construction to choose local or Daytona execution from configuration without changing `WorkspaceToolset` tool names or signatures.
- [x] 2.3 Preserve existing language validation, entrypoint path validation, UTF-8 read behavior, and dependency installation command blocking before remote execution starts.
- [x] 2.4 Normalize Daytona execution responses into the existing `WorkspaceExecutionResult` fields.

## 3. Daytona Sandbox Runtime Behavior

- [x] 3.1 Create or obtain a Daytona sandbox for each workspace code run with SmartClass labels for run id, thread id, plan id when available, agent name when available, and purpose.
- [x] 3.2 Upload required local workspace files into a sandbox work directory before executing the entrypoint.
- [x] 3.3 Execute Python and Node workspace entrypoints inside Daytona with remote `AGENT_WORKSPACE_ROOT`, `AGENT_RUN_ROOT`, and `AGENT_OUTPUT_DIR` environment variables.
- [x] 3.4 Download generated or changed output files from the sandbox output directory into the local run output directory.
- [x] 3.5 Return `output_files` as SmartClass workspace-relative POSIX paths compatible with the existing artifact collection flow.

## 4. Safety, Lifecycle, And Observability

- [x] 4.1 Apply configured Daytona sandbox lifecycle policy after execution, including stop, delete, or auto-cleanup settings.
- [x] 4.2 Apply configured Daytona network policy during sandbox creation or before execution.
- [x] 4.3 Map Daytona API, service, timeout, nonzero exit, output collection, and cleanup failures into clear internal error categories and user-readable summaries.
- [x] 4.4 Add structured logs for backend type, sandbox id or name, run id, thread id, plan id, language, entrypoint, duration, status, and error category.
- [x] 4.5 Ensure stdout, stderr, progress details, artifact trace content, and logs remain truncated and never include full secret values.

## 5. Tests And Verification

- [x] 5.1 Add tests that local backend behavior remains unchanged when Daytona is not enabled.
- [x] 5.2 Add tests for Daytona backend configuration validation and missing configuration failures.
- [x] 5.3 Add mock Daytona backend tests for sandbox creation labels, file upload, process execution, output download, and cleanup.
- [x] 5.4 Add failure tests for path traversal, blocked dependency install commands, unsupported language, nonzero exit, timeout, Daytona service error, and cleanup failure.
- [x] 5.5 Run the relevant backend test suite and record any skipped Daytona live-integration checks.

## 6. Rollout Checks

- [x] 6.1 Verify an existing PPT, DOCX, or HTML artifact generation path can still execute through the local backend.
- [x] 6.2 Verify the same representative artifact generation path can execute through Daytona in a configured development environment.
- [x] 6.3 Confirm generated files are copied into the existing artifact storage flow and are not left only inside Daytona.
- [x] 6.4 Confirm switching the configuration back to the local backend is sufficient rollback.

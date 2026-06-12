## 1. Governance Contract

- [ ] 1.1 Add `backend/app/core/agent_governance.py` with Agent role identifiers, tool permission tiers, high-risk action types, governance decision statuses, audit record schema, and standardized error categories.
- [ ] 1.2 Add helpers to build governance runtime context from existing `RunnableConfig`, `RunContext`, user, plan, thread, artifact, and workspace metadata.
- [ ] 1.3 Add sanitization and summary helpers for governance audit inputs and outputs, including truncation and redaction for JWTs, passwords, URLs, object keys, host paths, prompts, attachment text, memory content, and long tool output.
- [ ] 1.4 Add unit tests for governance enums, context construction, audit record validation, sanitization, truncation, and error category mapping.

## 2. Tool Metadata And Policy

- [ ] 2.1 Register governance metadata for workspace tools: `list_workspace_files`, `read_workspace_file`, `write_workspace_file`, `replace_workspace_text`, and `run_workspace_code`.
- [ ] 2.2 Register governance metadata for sensitive skill, memory, RAG, artifact, storage, and attachment-analysis operations that are callable from Agent flows.
- [ ] 2.3 Add policy evaluation helpers that verify Agent role, permission tier, required runtime context, high-risk action flags, and existing approval requirements.
- [ ] 2.4 Wire policy checks into existing Agent middleware without changing public tool response shapes.
- [ ] 2.5 Add tests that governed tools cannot be exposed without permission metadata and that unknown Agent roles or missing required context are denied before protected actions run.

## 3. Workspace Governance Integration

- [ ] 3.1 Apply governance checks to workspace read, write, text replacement, and code execution tools while preserving existing path validation, UTF-8 behavior, response fields, timeout handling, and output collection.
- [ ] 3.2 Emit governance audit records for successful and failed workspace tool calls, including backend type, language, entrypoint summary, duration, permission tier, status, and standardized error category.
- [ ] 3.3 Map local and Daytona workspace validation, execution, timeout, synchronization, cleanup, and dependency-installation failures into the shared governance error taxonomy.
- [ ] 3.4 Add tests that path traversal, unsupported language, blocked dependency installation, missing context, and disallowed Agent role failures are denied before local process or Daytona sandbox execution starts.
- [ ] 3.5 Add tests that workspace output paths remain workspace-relative and do not expose host absolute paths in tool responses, audit records, progress details, or trace entries.

## 4. Agent Flow And Failure Handling

- [ ] 4.1 Add Agent role assignment for main-flow, attachment-analysis, artifact-generation, artifact-modification, memory-reflection, and evaluation-related flows.
- [ ] 4.2 Normalize graph, Agent, memory, RAG, file-processing, storage, artifact, model, timeout, and permission failures into shared error categories at the boundary where they are logged or surfaced.
- [ ] 4.3 Ensure SSE `error`, progress failures, artifact failures, and artifact trace errors expose user-readable summaries while internal audit and observation records retain sanitized diagnostic details.
- [ ] 4.4 Preserve existing approval interrupts for teaching elements, teaching plan review, and artifact modification target confirmation.
- [ ] 4.5 Add regression tests for approval preservation, artifact failed-state summaries, and safe chat stream error handling.

## 5. Ownership And File Chain Enforcement

- [ ] 5.1 Audit Agent paths that read plans, threads, knowledge files, attachments, memories, and artifacts to ensure checks use backend `user_id` plus relevant `plan_id`, `thread_id`, or `artifact_id`.
- [ ] 5.2 Ensure Agent-created or revised user-visible files are promoted through `ArtifactFile`, `artifact_service`, and `StorageService` rather than remaining only in the temporary workspace.
- [ ] 5.3 Add tests for cross-user or cross-thread resource denial in Agent-triggered file, memory, and artifact operations.
- [ ] 5.4 Add tests that attachment context stays on the attachment-file chain and is not treated as knowledge-file or artifact-file storage.

## 6. Governance Evaluation Harness

- [ ] 6.1 Create `backend/tests/evals/` with structured fixture types for input, context, expected route or Agent role, expected memory behavior, expected tool permission behavior, key assertions, and allowed fuzzy matching rules.
- [ ] 6.2 Add deterministic fixtures for intent routing across ordinary chat, teaching planning, and artifact modification.
- [ ] 6.3 Add deterministic fixtures for memory retrieval and memory write safety, including irrelevant memory exclusion and sensitive/low-confidence memory write denial.
- [ ] 6.4 Add deterministic fixtures for RAG use, attachment analysis, artifact generation, artifact modification, and workspace safety.
- [ ] 6.5 Add helpers that attach `run_id`, `thread_id`, `plan_id`, and `user_id` to eval failures for debugging.
- [ ] 6.6 Add documentation or examples showing how to add new governance eval cases without requiring live LLM calls by default.

## 7. Verification

- [ ] 7.1 Run focused backend tests for governance, workspace, observability/audit, approval, artifact flow, memory, RAG, and auth policy.
- [ ] 7.2 Run the governance eval suite and record any cases skipped because they require live models, external services, or Daytona.
- [ ] 7.3 Verify OpenSpec status reports `tasks` as done only after implementation tasks are complete.

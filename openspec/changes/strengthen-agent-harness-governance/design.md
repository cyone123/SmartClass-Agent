## Context

SmartClass already has a working teacher-facing Agent flow with LangGraph routing, memory loading and reflection, RAG, attachment analysis, artifact generation, artifact revision, SSE progress, and workspace execution. The current governance surface is real but fragmented: workspace path checks live in workspace tools, skill authorization lives in middleware, user ownership checks live in APIs/services, progress and trace events are generated in several modules, and failure handling uses a mix of local exceptions, strings, and status updates.

The next phase needs a stable Agent Harness contract that can be applied consistently across main-flow Agents, attachment-analysis Agents, artifact-generation Agents, artifact-modification Agents, memory-reflection Agents, and future evaluation Agents. The design must keep the current product flow intact: no new SSE event types are required, existing human approval interrupts remain, user ownership continues to come from backend `user_id`, and file access continues to use the correct knowledge, attachment, or artifact chain through `StorageService`.

## Goals / Non-Goals

**Goals:**

- Define Agent roles and responsibility boundaries in backend code and tests.
- Centralize tool permission tier metadata and policy decisions without changing every tool call shape.
- Require high-risk actions to be explicitly allowed, denied, or routed through existing approval/human-in-the-loop mechanisms.
- Emit structured Agent audit records with stable correlation fields and sanitized input/output summaries.
- Normalize Agent failure categories so backend logs, SSE errors, progress failures, artifact failures, and tests can assert the same classes of failure.
- Add a repeatable backend evaluation harness for governance-sensitive Agent behavior.
- Extend workspace execution so local and sandbox-backed execution use the same governance audit and error taxonomy.

**Non-Goals:**

- Do not replace the current LangGraph topology or rewrite the whole Agent runtime.
- Do not add organization/class/school RBAC beyond the existing user ownership model.
- Do not expose new frontend event types or change the current SSE contract.
- Do not add vendor-specific observability, evaluation, or tracing platforms.
- Do not remove existing JSONL/logging/trace behavior or existing workspace path and install-command checks.
- Do not automate over current confirmation interrupts for teaching elements, teaching plans, or artifact modification targets.

## Decisions

### Decision 1: Add a small governance core as the integration boundary

Create a backend governance module, for example `backend/app/core/agent_governance.py`, that owns Agent role names, tool permission tiers, high-risk action definitions, audit record schemas, and error categories. Existing graph, agent, workspace, memory, RAG, storage, and artifact code should call this boundary rather than each inventing its own strings.

Rationale:

- The project already treats Agent behavior as a protocol problem across modules.
- A central module keeps policy vocabulary stable while allowing implementation to remain incremental.
- Tests and evals can import one contract instead of asserting scattered string literals.

Alternatives considered:

- Put policy into prompts only. This is rejected because prompts cannot enforce backend permission, audit, or error behavior.
- Create a large new Agent framework. This is unnecessary for the current phase and risks disrupting working flows.

### Decision 2: Use declarative tool metadata plus runtime context checks

Each governed tool should have metadata describing its permission tier, allowed Agent roles, required context fields, and high-risk action flags. Runtime checks should still validate concrete ownership and context such as `user_id`, `plan_id`, `thread_id`, `artifact_id`, and workspace root.

Rationale:

- Static metadata makes policy inspectable and testable.
- Runtime checks are still required because resource ownership comes from database state and current request context.
- Existing middleware such as skill execution policy can be adapted to use the shared vocabulary.

Alternatives considered:

- Only check permissions at API route boundaries. This misses Agent-internal tool calls.
- Only check permissions inside individual tools. This duplicates policy and makes coverage hard to prove.

### Decision 3: Standardize audit records before adding new storage

Introduce a structured audit record shape and route it through existing logging/observability paths first. Persisted audit tables can be added later if needed, but this change should establish fields, redaction, truncation, and failure isolation now.

Rationale:

- Current AGENTS guidance prioritizes traceability and privacy, not necessarily a new database table.
- Existing observation sinks already support sanitized runtime events.
- Keeping persistence out of the first change lowers migration risk.

Alternatives considered:

- Add a dedicated database audit table immediately. This may be useful later, but it introduces schema migration, retention, and privacy decisions before the contract is validated.
- Put full tool inputs and outputs in logs. This is rejected because prompts, attachment text, memory content, JWTs, object keys, URLs, and full model context can be sensitive.

### Decision 4: Make failure categories shared and user-visible only as summaries

Define a fixed error taxonomy for model, tool, permission, user-input, file-processing, storage, memory, RAG, artifact, timeout, external-service, and unknown failures. Internal records carry the category and sanitized details; SSE `error`, progress, and artifact failure fields expose a user-readable summary.

Rationale:

- Evaluation cases need deterministic failure categories.
- Frontend users need understandable errors without seeing internal stack traces.
- Backend operators need correlation fields for debugging.

Alternatives considered:

- Continue using ad hoc exception messages. This makes regression checks brittle.
- Expose internal exception details to the frontend. This leaks implementation and possible sensitive content.

### Decision 5: Build eval fixtures as structured backend tests

Create a focused `backend/tests/evals/` area with fixtures that describe input, context, expected route, expected memory behavior, expected tool permission behavior, and key assertions. For model-dependent flows, tests should prefer deterministic fakes or rubric helpers with structured assertions instead of brittle full-text snapshots.

Rationale:

- The project needs a repeatable Agent evaluation harness, not one-off manual validation.
- Structured fixtures let failures connect back to `run_id`, `thread_id`, `user_id`, and trace records.
- Deterministic fakes keep CI useful without requiring live LLM calls for every governance check.

Alternatives considered:

- Add only unit tests around the new policy module. Useful but insufficient for graph routing, memory, RAG, and artifact flows.
- Depend on live model outputs for every eval. This is expensive and nondeterministic.

## Risks / Trade-offs

- Policy metadata can drift from tool implementation -> Add tests that enumerate governed tools and assert metadata exists for sensitive tools.
- Too much centralization can slow feature work -> Keep the governance core small and vocabulary-focused, while resource ownership remains in services and APIs.
- Audit records can leak sensitive content -> Use summaries, truncation, allowlisted fields, and explicit tests that reject JWTs, full attachment text, full memory content, object keys, URLs, and host paths.
- Error categories can be too coarse -> Start with stable top-level categories and allow internal details to carry sanitized subreason fields.
- Eval cases can become brittle -> Use deterministic fakes and structured assertions for routing, permissions, memory behavior, and artifact state rather than snapshotting whole LLM responses.
- Existing flows may emit partial audit data at first -> Treat missing optional fields as acceptable only when the context genuinely lacks them; require `run_id`, `agent_name`, `tool_name`, status, and error category where applicable.

## Migration Plan

1. Add governance schemas, enums, and helpers for Agent roles, permission tiers, high-risk actions, audit records, and error categories.
2. Register metadata for existing sensitive tools, starting with workspace, skill, storage/artifact, memory, RAG, and attachment-analysis calls.
3. Wire policy checks into existing Agent middleware and workspace execution without changing public tool response shapes.
4. Emit structured audit records through existing observability/logging paths and ensure sink failures do not affect user workflows.
5. Normalize failures in chat streaming, graph nodes, workspace execution, artifact generation/modification, memory reflection, and file/RAG processing.
6. Add evaluation fixtures and tests for routing, memory, RAG, artifact modification, workspace safety, unauthorized resources, and user-readable failures.
7. Update documentation or local examples for adding new governed tools and eval cases.

Rollback strategy: remove the new governance enforcement hook or run it in audit-only mode while keeping existing workspace, auth, storage, and approval checks. Existing SSE and artifact contracts remain unchanged.

## Open Questions

- Should the first implementation include an audit-only mode for policy rollout, or should all registered high-risk denials be enforced immediately?
- Which exact memory writes should require explicit user confirmation versus policy-only confidence checks in the first iteration?
- Should audit records be persisted in a database table after the initial logging/observability contract stabilizes?

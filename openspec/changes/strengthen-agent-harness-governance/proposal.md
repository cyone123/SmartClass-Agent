## Why

SmartClass has entered the Agent Harness governance phase, but current guardrails, tool policy, trace metadata, error categories, and evaluation checks are still spread across graph, agent, workspace, memory, storage, and artifact paths. This makes Agent behavior harder to audit, compare, and regress-test as new capabilities are added.

This change establishes a unified governance contract for Agent execution so future work can be controlled, observable, and evaluable without bypassing existing authentication, storage, memory, workspace, SSE, and human-in-the-loop boundaries.

## What Changes

- Add a unified Agent governance capability that defines Agent roles, tool permission tiers, high-risk action policy decisions, audit event shape, error categories, and evaluation trace requirements.
- Add a centralized policy model for tool calls and Agent actions, including read-only, workspace-write, code-execution, object-storage-write, memory-write, and external-network tiers.
- Add structured audit records for Agent/tool activity with `run_id`, `thread_id`, `plan_id`, `user_id`, `agent_name`, `tool_name`, input/output summaries, duration, status, and error category.
- Add a consistent error taxonomy for Agent, graph, tool, storage, memory, RAG, artifact, file-processing, timeout, permission, and user-input failures.
- Add an evaluation harness under backend tests for intent routing, memory behavior, RAG use, artifact generation/modification, workspace safety, and failure visibility.
- Extend existing sandbox execution behavior so workspace tool calls participate in the same governance, audit, and evaluation contracts.
- Preserve existing SSE event types, artifact model, StorageService usage, user ownership checks, and approval interrupts.

## Capabilities

### New Capabilities

- `agent-harness-governance`: Defines how SmartClass Agent roles, tool permissions, high-risk action policy, audit records, failure categories, and evaluation cases are modeled and enforced.

### Modified Capabilities

- `agent-sandbox-execution`: Workspace execution remains isolated to the current run workspace, and now also emits governance audit records, uses standardized permission/error categories, and is covered by safety evaluation cases.

## Impact

- Backend core: `backend/app/core/agent.py`, `backend/app/core/graph.py`, `backend/app/core/skills.py`, `backend/app/core/workspace.py`, `backend/app/core/progress.py`, `backend/app/core/memory.py`, `backend/app/core/rag.py`, and related middleware/policy helpers.
- Backend services: file, artifact, storage, memory, and attachment-analysis flows that invoke Agent tools or persist Agent-created outputs.
- Backend APIs: chat streaming and memory/file/artifact routes should keep current auth and ownership checks while exposing user-readable failure summaries through existing SSE contracts.
- Tests and evals: add `backend/tests/evals/` or an equivalent focused test area for governance and Agent regression cases.
- Documentation/specs: add explicit contracts for Agent roles, permission tiers, audit event fields, error categories, and evaluation fixtures.

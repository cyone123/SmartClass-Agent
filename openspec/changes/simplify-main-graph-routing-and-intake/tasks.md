## 1. Establish Action and State Contracts

- [x] 1.1 Add typed schemas for `start_teaching_design`, `revise_artifact`, and `submit_metadata_for_review`, including field budgets, supported artifact targets, and required final metadata validation; verify unit tests reject unknown, multiple, malformed, excessive, and mixed text/action results.
- [x] 1.2 Add explicit active teaching-task boundary state and lifecycle helpers without adding per-turn partial metadata; verify tests cover start, clarification resume, cancellation, task replacement, metadata submission, and completion resets.
- [x] 1.3 Build a bounded current-task intake message selector that preserves the initial request, intake questions, user corrections, and attachment summaries while excluding earlier tasks, protocol messages, RAG chunks, memory bodies, and repeated attachment bodies; verify focused context-selection and budget tests pass.
- [x] 1.4 Add sanitized observation fields for entry outcomes, validation/repair/fallback outcomes, task-scope transitions, and model-call counts; verify observability tests prove sensitive prompt, metadata, memory, attachment, identifier, URL, object-key, and host-path values are not recorded as metric labels.

## 2. Implement the Conversation Entry Agent

- [x] 2.1 Define and test the entry system prompt and tool binding so ordinary text, teaching-design actions, artifact-revision actions, and mixed greeting/teaching requests are mutually exclusive and route correctly.
- [x] 2.2 Implement bounded local action dispatch to graph commands without a general-purpose tool node, preserving `intent`, `teaching_task_initial_request`, trusted artifact-catalog revision context, and existing revision targets; verify graph unit tests cover all three outcomes.
- [x] 2.3 Add one bounded repair attempt and configured reliable-model fallback for invalid entry output while reusing the same Profile and resolved turn-memory context; verify failure-injection tests produce one safe outcome without duplicate workflow execution.
- [x] 2.4 Add the optional one-search ordinary-chat Experience round with authenticated identity, strict result limits, and no task-snapshot promotion; verify memory tests distinguish simple one-call chat, memory-assisted chat, and teaching-design actions without prefetching Experience for intake.

## 3. Implement Conversational Teaching Intake

- [x] 3.1 Implement the intake model call over bounded active-task messages so incomplete requests return exactly one visible clarification and do not write partial `teaching_metadata`; verify incomplete, multi-turn, old-task-contamination, Profile-non-inference, and attachment-budget tests.
- [x] 3.2 Dispatch visible intake questions to the existing generic clarification interrupt and resume directly into intake with text or attachment replies; verify checkpoint tests prove the entry model is not re-invoked and no approval payload is emitted.
- [x] 3.3 Implement final metadata action validation and canonical snapshot creation with backend-owned `is_complete=true`; verify valid complete requests enter metadata review and invalid submissions repair or clarify without exposing tool protocol.
- [x] 3.4 Route metadata-review rejection and explicit corrections back to intake with the last submitted snapshot as bounded context; verify corrected metadata requires a new interrupt and the original model work is not repeated on approval resume.
- [x] 3.5 Handle explicit cancel and replacement requests during intake, closing or restarting the active task boundary without submitting stale metadata; verify end-to-end graph tests cover both outcomes.

## 4. Recompose the Main Graph and Preserve Checkpoints

- [x] 4.1 Replace the dedicated intent router plus ordinary-chat node with the conversation entry agent and replace metadata structuring/completeness/follow-up nodes with the intake agent while retaining Profile bootstrap, generic clarification, both approval interrupts, revision flow, artifact branches, and fan-in; verify graph topology tests assert the simplified paths.
- [x] 4.2 Keep model work outside interrupt nodes and update interrupt outgoing routes to the new intake/context boundaries; verify replay tests prove clarification, metadata approval, metadata correction, and teaching-plan approval do not re-run pre-interrupt model calls.
- [x] 4.3 Add thin forwarding aliases or an equivalent migration path for pending checkpoints that reference removed node names; verify simulated legacy snapshots resume successfully without invoking legacy model logic.
- [x] 4.4 Add a configuration-controlled rollout and rollback path, defaulting to the legacy graph until the regression gates pass; verify both configurations compile and preserve compatible state and approval payloads.

## 5. Prepare Post-Approval Teaching Context

- [x] 5.1 Introduce a post-metadata-approval context-preparation boundary that runs bounded RAG retrieval and teaching-task Experience resolution concurrently when both are enabled; verify concurrency and independent success/degradation unit tests.
- [x] 5.2 Preserve the existing task-scope key and checkpointed Experience snapshot across teaching planning, plan approval resume, and all artifact-generation branches; verify one retrieval occurs for an unchanged scope and every branch receives the same bounded snapshot.
- [x] 5.3 Invalidate and refresh the Experience snapshot exactly once when an approved correction changes retrieval-significant metadata while leaving artifact-only revisions reusable; verify scope-key and fan-out tests cover both cases.
- [x] 5.4 Preserve fail-open behavior and distinct provenance for optional RAG and Experience failures; verify the planner continues with available context and observations report sanitized degraded outcomes.

## 6. Preserve SSE and Frontend Behavior

- [x] 6.1 Add the new entry and intake nodes to root text streaming and filter protocol-only tool calls, conflicting preambles, and empty messages; verify stream tests cover ordinary tokens, intake questions, action-only turns, and no blank assistant bubbles.
- [x] 6.2 Preserve the existing SSE event allowlists, sequencing, replay, terminal events, progress keys, and `metadata_review`/`teaching_plan_review` approval payloads; verify backend durable-run tests cover initial delivery, reconnect, stale approval, clarification resume, and waiting-approval status.
- [x] 6.3 Update progress labels only where needed to describe consolidated entry/intake work without changing stable keys; verify frontend progress cards render all running, success, failed, and approval transitions.
- [x] 6.4 Extend frontend stream tests to assert metadata and plan approval cards remain compatible, intake questions render as text, tool arguments never render, and reconnect does not duplicate cards or messages; verify `npm run build` and the frontend stream test command pass.

## 7. Update Evaluation and Regression Evidence

- [x] 7.1 Refactor intent and extraction evaluators to assert entry actions, visible responses, canonical final metadata, and pending interrupt state rather than importing removed node functions; verify the offline suite still validates with the expected 24 cases.
- [x] 7.2 Expand model-eval cases for mixed intent, artifact revision, incomplete multi-turn intake, corrections, cancellation/replacement, invalid tool output, Profile non-inference, and task-boundary isolation; verify each category reports `PASSED`, `FAILED`, and `ERROR` distinctly under Schema 2.0.
- [x] 7.3 Add deterministic approval, checkpoint migration, context compression, memory snapshot, SSE sequence, and sensitive-observation regression tests; verify the targeted backend test files pass on Windows-compatible asyncio settings.
- [x] 7.4 Capture pre-change and post-change model-call counts, first-token latency, clarification latency, and approval latency separately for ordinary chat, memory-assisted chat, first incomplete teaching requests, clarification turns, and complete requests; verify the report does not substitute average score for pass rate or contain sensitive raw content.
- [x] 7.5 Run `python -m ruff check app tests`, `python -m ruff format --check app tests`, the default `python -m pytest -q`, strict eval-suite validation, relevant explicit model/integration evaluations, frontend tests, and `npm run build`; fix all regressions before enabling the simplified graph by default.

## 8. Finalize Rollout Documentation

- [x] 8.1 Update backend workflow documentation and diagrams to describe action-based entry, message-based intake, final-only metadata materialization, durable interrupt boundaries, SSE behavior, and memory lifecycle; verify no documentation claims the removed nodes remain active.
- [x] 8.2 Document rollout flag behavior, rollback steps, legacy-checkpoint alias monitoring, and the criteria for removing compatibility aliases in a later change; verify operators can switch implementations without rewriting stored metadata, approvals, artifacts, or memory snapshots.
- [x] 8.3 Enable the simplified graph by default only after all required gates and comparison evidence pass, retain the rollback path for the compatibility window, and verify a smoke run completes ordinary chat, clarification, metadata approval, plan approval, artifact generation, and artifact revision.

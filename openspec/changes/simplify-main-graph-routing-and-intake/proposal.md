## Why

The main LangGraph currently separates intent classification, ordinary-chat response, metadata extraction, follow-up generation, and clarification waiting into several model and routing nodes. This increases ordinary-chat latency, repeats model work during multi-turn teaching intake, and couples workflow behavior to implementation-specific node names even though the user experience is fundamentally conversational.

## What Changes

- Replace the dedicated structured intent router plus ordinary-chat node with one tool-capable conversation entry agent that either answers directly or emits a validated workflow action for teaching design or artifact revision.
- Replace per-turn metadata extraction, completeness routing, and the separate follow-up model with one teaching-intake agent that reasons over the bounded current-task conversation.
- Keep incomplete teaching metadata in conversation history rather than materializing partial metadata after every turn; materialize and validate the complete metadata once, immediately before metadata review.
- Preserve a generic clarification interrupt so replies resume directly in teaching intake, while keeping metadata review and teaching-plan review as separate durable interrupt nodes.
- Preserve the existing artifact-revision route, artifact fan-out/fan-in, durable SSE event vocabulary, approval-card stages, and frontend rendering contracts.
- Resolve RAG context and the bounded teaching-task Experience snapshot only after metadata approval, then reuse the snapshot through planning, approval resume, and artifact generation.
- Add explicit task-boundary, tool-result, fallback, observability, context-budget, and evaluation requirements so the simplified graph remains deterministic and recoverable.

## Capabilities

### New Capabilities

- `conversational-teaching-orchestration`: Defines tool-driven conversation routing, iterative teaching-requirement collection, final metadata submission, durable clarification and approval boundaries, SSE visibility, and memory lifecycle requirements for the simplified main graph.

### Modified Capabilities

None. The existing durable chat-run event vocabulary and context-compression safety requirements remain compatible and are consumed without changing their public contracts.

## Impact

- Backend graph construction and node implementations in `backend/app/core/graph.py`.
- Model invocation, root-node token filtering, approval discovery, and stream orchestration in `backend/app/core/agent.py` and `backend/app/core/model_runtime.py`.
- Teaching state and task-boundary fields in `backend/app/core/state.py`.
- Progress labels and observations, while retaining the current replayable SSE event types.
- Frontend stream and approval-card behavior tests; production UI changes should be limited to wording unless contract testing exposes a compatibility gap.
- Intent, extraction, approval, memory, context-compression, observability, and end-to-end evaluation coverage.

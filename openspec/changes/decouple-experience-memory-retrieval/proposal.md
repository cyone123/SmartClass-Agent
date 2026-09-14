## Why

The first implementation removed fixed retrieval nodes, but Experience retrieval is still scoped too narrowly: query quality depends heavily on the latest message, artifact branches resolve similar memories independently, and the configured LangGraph Store does not actually enable semantic search. The design should treat Experience as bounded task context that is resolved once and shared across the teaching workflow, while keeping Profile as a simple session snapshot.

## What Changes

- Retain a dedicated session-start Profile load that renders the authenticated user's complete bounded Profile set once and reuses it throughout the session.
- Build Experience queries from a bounded teaching-task summary containing the initial request, recent relevant user clarifications, structured teaching metadata, and the current task/revision scope instead of relying primarily on the latest message.
- Enable LangGraph Store semantic search for Experience memories only, index bounded descriptive fields, preserve semantic ranking, and prevent silent fallback to recency when semantic search is expected.
- Resolve one bounded Experience snapshot for a teaching task and share it across teaching design, approval/resume, and PPT/DOCX/HTML artifact branches; refresh it only when the task scope materially changes.
- Keep eligible normal chat retrieval turn-scoped and keep the read-only on-demand Experience search tool for genuinely new questions discovered during Agent execution.
- Change `ModelRuntime` to accept an already resolved Experience bundle as well as an optional request, allowing business orchestration to own the sharing boundary.
- Replace artifact-agent retrieval middleware and per-agent caches with a task-start system-prompt render. Pass the pre-rendered prompt through LangChain runtime context and use a lightweight `@dynamic_prompt` hook only to supply the same prompt to each stateless model round.
- Preserve fail-open retrieval, account-scoped namespaces, bounded context, current-user-instruction precedence, privacy controls, and low-cardinality observability.
- Add semantic-search migration/backfill, real-Store integration tests, workflow-sharing tests, query-quality tests, and revised evaluation coverage.

## Capabilities

### New Capabilities

- `long-term-memory-retrieval`: Defines session-scoped Profile context, task-scoped shared Experience retrieval, semantic candidate search, common model-runtime integration, artifact dynamic-system-prompt integration, freshness, failure isolation, privacy, and observability.

### Modified Capabilities

- None.

## Impact

- Backend Store construction and embedding/index configuration in `backend/app/dependencies/db.py`, configuration modules, and environment templates.
- Long-term-memory write/search helpers in `backend/app/core/memory.py` and Experience request/provider behavior in `backend/app/core/memory_retrieval.py`.
- Task query construction, Experience snapshot state, routing/consumption boundaries, and model calls in `backend/app/core/graph.py`, `backend/app/core/state.py`, and `backend/app/core/model_runtime.py`.
- Artifact Agent construction and invocation context in `backend/app/core/agent.py`.
- Existing Experience rows require a bounded, idempotent semantic-index backfill path.
- Unit, integration, evaluation, configuration, and observability tests change. Public memory APIs, SSE events, memory content schema, Profile semantics, and reflection-worker behavior remain unchanged.

## 1. Persistent Run Foundation

- [x] 1.1 Add SQLAlchemy models for owned Agent runs and ordered run events, including lifecycle, input, output snapshot, sequence, and timestamps.
- [x] 1.2 Add chat-run request/response schemas and serialization helpers that exclude raw execution input from status responses.
- [x] 1.3 Implement run/event persistence operations, active-run conflict checks, replay queries, terminal transitions, and startup stale-run reconciliation.

## 2. Subscriber-Independent Execution

- [x] 2.1 Implement the in-process `ChatRunManager` that schedules backend-owned tasks, reloads attachments, drives `AgentRuntime.stream_agent_events()`, and persists supported events.
- [x] 2.2 Add explicit cancellation and application lifespan startup/shutdown integration without coupling task lifetime to an SSE subscriber.
- [x] 2.3 Preserve approval, context-compression, error, and terminal-status semantics in the durable event sequence.

## 3. Run API and Replay SSE

- [x] 3.1 Add authenticated run creation with existing thread, attachment, and approval validation and `202` response behavior.
- [x] 3.2 Add authorized run status, active-run discovery, and cancellation endpoints.
- [x] 3.3 Add ordered replay/follow SSE with event IDs, cursor parsing, heartbeats, terminal completion, and sanitized subscription observations.
- [x] 3.4 Keep the legacy `/api/chat/stream` endpoint compatible and update Nginx routing for the new replay stream path.

## 4. Frontend Reconnection

- [x] 4.1 Add frontend chat-run API helpers for create, status, active discovery, cancellation, and authenticated replay streaming.
- [x] 4.2 Extend Pinia session state with per-thread run id, lifecycle status, last sequence, output snapshot, and subscription-only abort state.
- [x] 4.3 Refactor ChatPanel submission and event consumption to create then subscribe, ignore duplicate sequences, and retry transient disconnects with bounded backoff.
- [x] 4.4 Reattach when returning to a thread, abort only the prior subscription on session switch/unmount, and reconcile terminal runs with message/artifact history.

## 5. Verification and Documentation

- [x] 5.1 Add backend service/API tests for event ordering and replay, subscriber disconnect independence, lifecycle transitions, ownership, conflicts, cancellation, approval, and stale-run reconciliation.
- [x] 5.2 Add or extend frontend-verifiable behavior coverage and run the production frontend build.
- [x] 5.3 Run backend pytest and Ruff gates relevant to the change, fix regressions, and document the MVP reliability boundary and phase-two follow-up.

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.api.chat as chat_api
import app.core.chat_runs as chat_runs_module
from app.api.chat import format_sse_json_event
from app.api.chat import router as chat_router
from app.core.agent import get_agent_runtime
from app.core.auth import get_current_user
from app.core.chat_run_events import (
    ChatRunEvent,
    ChatRunEventStoreError,
    ChatRunEventStoreUnavailable,
    ChatRunLiveSnapshot,
    get_chat_run_redis,
)
from app.core.chat_runs import ChatRunManager, get_chat_run_manager
from app.core.model_access.workflow import capture_envelope
from app.dependencies.db import get_db
from app.services import chat_run_service, session_service


class _AsyncSessionContext:
    def __init__(self, value=None) -> None:
        self.value = value if value is not None else object()

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb


def _run_record(*, status: str = "queued", last_event_sequence: int = 0) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        run_id="run-1",
        thread_id="thread-1",
        user_id=7,
        plan_id=11,
        status=status,
        message="hello",
        attachment_ids=[],
        approval=None,
        model_config_snapshot=capture_envelope().model_dump(mode="json"),
        output_text="",
        last_event_sequence=last_event_sequence,
        error_message=None,
        created_at=now,
        started_at=None,
        completed_at=None,
    )


class _MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[tuple[int, str, dict]] = []
        self.output = ""
        self.ready = True
        self.fail_append = False

    async def ensure_ready(self) -> None:
        if not self.ready:
            raise ChatRunEventStoreUnavailable("Chat run event storage is unavailable.")

    async def append(self, run_id: str, event_type: str, payload: dict) -> int:
        _ = run_id
        if self.fail_append:
            raise ChatRunEventStoreError("Chat run event storage operation failed.")
        sequence = len(self.events) + 1
        self.events.append((sequence, event_type, payload))
        if event_type == "token":
            self.output += str(payload.get("text") or "")
        return sequence

    async def get_snapshot(self, run_id: str):
        _ = run_id
        if not self.events:
            return None
        return ChatRunLiveSnapshot(last_sequence=len(self.events), output_text=self.output)

    async def append_done(self, run_id: str, *, sequence: int, status: str) -> bool:
        if self.fail_append:
            raise ChatRunEventStoreError("Chat run event storage operation failed.")
        if any(item[0] == sequence for item in self.events):
            return False
        self.events.append((sequence, "done", {"run_id": run_id, "status": status}))
        return True


def test_sse_event_includes_replay_sequence() -> None:
    event = format_sse_json_event({"run_id": "run-1", "text": "ok"}, event="token", event_id=12)
    assert event.startswith("id: 12\nevent: token\n")
    assert 'data: {"run_id": "run-1", "text": "ok"}' in event


def test_chat_run_serialization_uses_redis_only_for_active_projection() -> None:
    active = _run_record(status=chat_run_service.RUN_STATUS_RUNNING, last_event_sequence=1)
    active.output_text = "postgres-old"
    live = ChatRunLiveSnapshot(last_sequence=4, output_text="redis-live")
    active_payload = chat_run_service.serialize_chat_run(active, live_snapshot=live)
    assert active_payload["last_event_sequence"] == 4
    assert active_payload["output_text"] == "redis-live"

    terminal = _run_record(status=chat_run_service.RUN_STATUS_SUCCEEDED, last_event_sequence=8)
    terminal.output_text = "postgres-final"
    terminal_payload = chat_run_service.serialize_chat_run(terminal, live_snapshot=live)
    assert terminal_payload["last_event_sequence"] == 8
    assert terminal_payload["output_text"] == "postgres-final"
    assert "message" not in terminal_payload


def test_manager_runs_without_subscriber_and_preserves_event_order(monkeypatch) -> None:
    run = _run_record(status=chat_run_service.RUN_STATUS_RUNNING)
    store = _MemoryEventStore()
    finalized: list[tuple[str, str, int]] = []

    class FakeRuntime:
        async def stream_agent_events(self, *args, **kwargs):
            _ = args, kwargs
            yield {"event": "token", "data": {"text": "a"}}
            yield {"event": "token", "data": {"text": "b"}}
            yield {"event": "progress", "data": {"steps": []}}
            yield {"event": "artifact", "data": {"artifact_id": 1}}

    async def fake_mark_running(db, run_id):
        _ = db, run_id
        return run

    async def fake_finalize(db, *, run_id, status, output_text, last_sequence, error_message=None):
        _ = db, run_id, error_message
        run.status = status
        run.output_text = output_text
        run.last_event_sequence = last_sequence + 1
        finalized.append((status, output_text, run.last_event_sequence))
        return run

    monkeypatch.setattr(chat_runs_module, "AsyncSessionLocal", lambda: _AsyncSessionContext())
    monkeypatch.setattr(chat_run_service, "mark_chat_run_running", fake_mark_running)
    monkeypatch.setattr(chat_run_service, "finalize_chat_run", fake_finalize)

    async def exercise() -> None:
        manager = ChatRunManager(FakeRuntime(), store)
        manager.schedule(run.run_id)
        await manager._tasks[run.run_id]

    asyncio.run(exercise())
    assert [(event_type, payload.get("text")) for _, event_type, payload in store.events] == [
        ("metadata", None),
        ("token", "ab"),
        ("progress", None),
        ("artifact", None),
        ("done", None),
    ]
    assert finalized == [(chat_run_service.RUN_STATUS_SUCCEEDED, "ab", 5)]


def test_manager_preserves_approval_and_explicit_cancellation(monkeypatch) -> None:
    approval_run = _run_record(status=chat_run_service.RUN_STATUS_RUNNING)
    cancel_run = _run_record(status=chat_run_service.RUN_STATUS_RUNNING)
    cancel_run.run_id = "run-cancel"
    store = _MemoryEventStore()
    cancel_started = asyncio.Event()
    finalized = []

    class FakeRuntime:
        async def cancel_model_workflow(self, thread_id):
            assert thread_id == "thread-1"

        async def stream_agent_events(self, *args, **kwargs):
            _ = args
            if kwargs["run_id"] == approval_run.run_id:
                yield {"event": "approval", "data": {"interrupt_id": "i-1"}}
                return
            cancel_started.set()
            await asyncio.Event().wait()
            if False:
                yield {}

    async def fake_mark_running(db, run_id):
        _ = db
        return approval_run if run_id == approval_run.run_id else cancel_run

    async def fake_finalize(db, **kwargs):
        _ = db
        target = approval_run if kwargs["run_id"] == approval_run.run_id else cancel_run
        target.status = kwargs["status"]
        target.last_event_sequence = kwargs["last_sequence"] + 1
        finalized.append((kwargs["run_id"], kwargs["status"]))
        return target

    monkeypatch.setattr(chat_runs_module, "AsyncSessionLocal", lambda: _AsyncSessionContext())
    monkeypatch.setattr(chat_run_service, "mark_chat_run_running", fake_mark_running)
    monkeypatch.setattr(chat_run_service, "finalize_chat_run", fake_finalize)

    async def exercise() -> None:
        manager = ChatRunManager(FakeRuntime(), store)
        manager.schedule(approval_run.run_id)
        await manager._tasks[approval_run.run_id]
        manager.schedule(cancel_run.run_id)
        await cancel_started.wait()
        await manager.cancel(cancel_run.run_id)

    asyncio.run(exercise())
    assert (approval_run.run_id, chat_run_service.RUN_STATUS_WAITING_APPROVAL) in finalized
    assert (cancel_run.run_id, chat_run_service.RUN_STATUS_CANCELLED) in finalized


def test_redis_append_failure_finalizes_failed_run_without_postgres_event_fallback(monkeypatch) -> None:
    run = _run_record(status=chat_run_service.RUN_STATUS_RUNNING)

    class Store(_MemoryEventStore):
        async def append(self, run_id: str, event_type: str, payload: dict) -> int:
            if event_type == "metadata":
                return await super().append(run_id, event_type, payload)
            raise ChatRunEventStoreError("Chat run event storage operation failed.")

    store = Store()
    finalized = []

    class FakeRuntime:
        async def stream_agent_events(self, *args, **kwargs):
            _ = args, kwargs
            yield {"event": "token", "data": {"text": "locally-known"}}
            yield {"event": "progress", "data": {"steps": []}}

    async def fake_mark_running(db, run_id):
        _ = db, run_id
        return run

    async def fake_finalize(db, **kwargs):
        _ = db
        finalized.append(kwargs)
        run.status = kwargs["status"]
        run.output_text = kwargs["output_text"]
        run.last_event_sequence = kwargs["last_sequence"] + 1
        return run

    monkeypatch.setattr(chat_runs_module, "AsyncSessionLocal", lambda: _AsyncSessionContext())
    monkeypatch.setattr(chat_run_service, "mark_chat_run_running", fake_mark_running)
    monkeypatch.setattr(chat_run_service, "finalize_chat_run", fake_finalize)

    async def exercise() -> None:
        manager = ChatRunManager(FakeRuntime(), store)
        manager.schedule(run.run_id)
        await manager._tasks[run.run_id]

    asyncio.run(exercise())
    assert finalized[-1]["status"] == chat_run_service.RUN_STATUS_FAILED
    assert finalized[-1]["last_sequence"] == 1
    assert finalized[-1]["output_text"] == "locally-known"
    assert finalized[-1]["error_message"] == "对话处理失败，请稍后重试。"


def test_terminal_snapshot_commits_before_done_and_tolerates_redis_race(monkeypatch) -> None:
    run = _run_record(status=chat_run_service.RUN_STATUS_RUNNING)
    order = []

    class Store(_MemoryEventStore):
        async def append_done(self, run_id: str, *, sequence: int, status: str) -> bool:
            _ = run_id, sequence, status
            order.append("redis_done")
            raise ChatRunEventStoreError("safe failure")

    async def fake_finalize(db, **kwargs):
        _ = db
        order.append("postgres")
        run.status = kwargs["status"]
        run.output_text = kwargs["output_text"]
        run.last_event_sequence = kwargs["last_sequence"] + 1
        return run

    monkeypatch.setattr(chat_runs_module, "AsyncSessionLocal", lambda: _AsyncSessionContext())
    monkeypatch.setattr(chat_run_service, "finalize_chat_run", fake_finalize)

    async def exercise() -> None:
        manager = ChatRunManager(SimpleNamespace(), Store())
        finalized = await manager._finalize_run(
            run.run_id,
            status=chat_run_service.RUN_STATUS_SUCCEEDED,
            fallback_output="complete",
            fallback_sequence=4,
        )
        assert finalized.output_text == "complete"
        assert finalized.last_event_sequence == 5

    asyncio.run(exercise())
    assert order == ["postgres", "redis_done"]


def test_startup_reconciliation_uses_redis_snapshot_and_exposes_one_done(monkeypatch) -> None:
    run = _run_record(status=chat_run_service.RUN_STATUS_RUNNING)
    store = _MemoryEventStore()
    store.events = [(1, "token", {"text": "partial"})]
    store.output = "partial"
    finalized = []

    async def fake_stale(db):
        _ = db
        return [run]

    async def fake_finalize(db, **kwargs):
        _ = db
        finalized.append(kwargs)
        run.status = kwargs["status"]
        run.output_text = kwargs["output_text"]
        run.last_event_sequence = kwargs["last_sequence"] + 1
        return run

    monkeypatch.setattr(chat_runs_module, "AsyncSessionLocal", lambda: _AsyncSessionContext())
    monkeypatch.setattr(chat_run_service, "list_stale_chat_runs", fake_stale)
    monkeypatch.setattr(chat_run_service, "finalize_chat_run", fake_finalize)

    asyncio.run(ChatRunManager(SimpleNamespace(), store).start())
    assert finalized[0]["status"] == chat_run_service.RUN_STATUS_FAILED
    assert finalized[0]["output_text"] == "partial"
    assert [event_type for _, event_type, _ in store.events].count("done") == 1
    assert [event_type for _, event_type, _ in store.events] == ["token", "error", "done"]


def test_create_run_checks_redis_before_persisting_or_scheduling(monkeypatch) -> None:
    run = _run_record()
    store = _MemoryEventStore()
    created = []
    scheduled = []

    class FakeRuntime:
        async def validate_approval_request(self, thread_id, interrupt_id):
            _ = thread_id, interrupt_id

        async def get_memory_reflection_checkpoint_values(self, thread_id):
            return None

    class FakeManager:
        def schedule(self, run_id):
            scheduled.append(run_id)

    async def fake_get_session(db, thread_id, *, user_id=None):
        _ = db, thread_id, user_id
        return SimpleNamespace(plan_id=11)

    async def fake_create(db, **kwargs):
        _ = db
        created.append(kwargs)
        return run

    monkeypatch.setattr(session_service, "get_session_by_thread_id", fake_get_session)
    monkeypatch.setattr(chat_run_service, "create_chat_run", fake_create)

    async def request(ready: bool):
        store.ready = ready
        app = FastAPI()
        app.include_router(chat_router)

        async def override_db():
            yield None

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_agent_runtime] = lambda: FakeRuntime()
        app.dependency_overrides[get_chat_run_manager] = lambda: FakeManager()
        app.dependency_overrides[get_chat_run_redis] = lambda: store
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            return await client.post("/chat/runs", json={"thread_id": "thread-1", "message": "hello"})

    unavailable = asyncio.run(request(False))
    assert unavailable.status_code == 503
    assert created == []
    assert scheduled == []

    accepted = asyncio.run(request(True))
    assert accepted.status_code == 202
    assert len(created) == 1
    assert scheduled == [run.run_id]


def test_active_run_api_checks_ownership_and_overlays_snapshot(monkeypatch) -> None:
    run = _run_record(status=chat_run_service.RUN_STATUS_RUNNING)
    store = _MemoryEventStore()
    store.events = [(1, "token", {"text": "live"})]
    store.output = "live"
    checked = []

    async def fake_ensure(db, thread_id, *, user_id):
        _ = db
        checked.append((thread_id, user_id))

    async def fake_active(db, *, thread_id, user_id):
        _ = db, thread_id, user_id
        return run

    monkeypatch.setattr(session_service, "ensure_owned_session_by_thread_id", fake_ensure)
    monkeypatch.setattr(chat_run_service, "get_active_chat_run", fake_active)

    async def exercise() -> None:
        app = FastAPI()
        app.include_router(chat_router)

        async def override_db():
            yield None

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_chat_run_redis] = lambda: store
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get("/chat/runs/active", params={"thread_id": "thread-1"})
        assert response.status_code == 200
        assert response.json()["run"]["output_text"] == "live"

    asyncio.run(exercise())
    assert checked == [("thread-1", 7)]


def test_sse_replays_cursor_and_synthesizes_missing_terminal_done(monkeypatch) -> None:
    run = _run_record(status=chat_run_service.RUN_STATUS_SUCCEEDED, last_event_sequence=3)
    now = datetime.now(timezone.utc)

    class EventStore(_MemoryEventStore):
        async def read_after(self, run_id, after_sequence):
            _ = run_id
            if after_sequence < 2:
                return [
                    ChatRunEvent(
                        run_id=run.run_id,
                        sequence=2,
                        event_type="token",
                        payload={"run_id": run.run_id, "text": "ok"},
                        created_at=now,
                    )
                ]
            return []

    store = EventStore()

    async def fake_owned(db, run_id, *, user_id):
        _ = db, user_id
        return run if run_id == run.run_id else None

    async def fake_get(db, run_id):
        _ = db, run_id
        return run

    monkeypatch.setattr(chat_run_service, "get_owned_chat_run", fake_owned)
    monkeypatch.setattr(chat_run_service, "get_chat_run", fake_get)
    monkeypatch.setattr(chat_api, "AsyncSessionLocal", lambda: _AsyncSessionContext())

    async def exercise() -> None:
        app = FastAPI()
        app.include_router(chat_router)

        async def override_db():
            yield None

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_chat_run_redis] = lambda: store
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            replay = await client.get(f"/chat/runs/{run.run_id}/events", headers={"Last-Event-ID": "1"})
            forbidden = await client.get("/chat/runs/unknown/events")
        assert replay.status_code == 200
        assert "id: 1" not in replay.text
        assert "id: 2\nevent: token" in replay.text
        assert replay.text.count("event: done") == 1
        assert "id: 3\nevent: done" in replay.text
        assert forbidden.status_code == 404

    asyncio.run(exercise())


def test_sse_emits_heartbeat_while_waiting_then_one_terminal_event(monkeypatch) -> None:
    active_run = _run_record(status=chat_run_service.RUN_STATUS_RUNNING, last_event_sequence=0)
    terminal_run = _run_record(status=chat_run_service.RUN_STATUS_SUCCEEDED, last_event_sequence=1)
    terminal_run.run_id = active_run.run_id
    reads = 0

    class EventStore(_MemoryEventStore):
        async def read_after(self, run_id, after_sequence):
            nonlocal reads
            _ = run_id, after_sequence
            reads += 1
            return []

    store = EventStore()

    async def fake_owned(db, run_id, *, user_id):
        _ = db, user_id
        return active_run if run_id == active_run.run_id else None

    async def fake_get(db, run_id):
        _ = db, run_id
        return active_run if reads == 1 else terminal_run

    monkeypatch.setattr(chat_run_service, "get_owned_chat_run", fake_owned)
    monkeypatch.setattr(chat_run_service, "get_chat_run", fake_get)
    monkeypatch.setattr(chat_api, "AsyncSessionLocal", lambda: _AsyncSessionContext())

    async def exercise() -> None:
        app = FastAPI()
        app.include_router(chat_router)

        async def override_db():
            yield None

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_chat_run_redis] = lambda: store
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get(f"/chat/runs/{active_run.run_id}/events")
        assert response.status_code == 200
        assert response.text.count(": keep-alive") == 1
        assert response.text.count("event: done") == 1
        assert "id: 1\nevent: done" in response.text

    asyncio.run(exercise())

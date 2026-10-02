from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import config
from app.api.memory import router as memory_router
from app.core import graph
from app.core import memory as memory_module
from app.core.agent import get_agent_runtime
from app.core.auth import get_current_user
from app.core.chat_runs import ChatRunManager
from app.core.memory import extract_profile_memory_proposal, profile_namespace
from app.core.memory_worker import MemoryReflectionWorker
from app.core.observability import (
    ObservationEvent,
    PrometheusObservationSink,
    RunContext,
    assert_prometheus_labels_are_bounded,
)
from app.dependencies.db import get_db
from app.migrations.v20260912_memory_reflection_jobs import upgrade
from app.models.agent_run import AgentRun
from app.models.memory_reflection import MemoryMutationGuard, MemoryReflectionJob
from app.schemas.memory_reflection import (
    ExperienceReflectionSnapshot,
    MemoryMutationProposal,
    ProfileReflectionSnapshot,
)
from app.services import chat_run_service
from app.services.memory_reflection_service import (
    JOB_FAILED,
    JOB_SKIPPED,
    MemoryReflectionJobRepository,
    ReflectionJobCandidate,
    build_reflection_job_candidates,
    register_reflection_candidates,
    wait_for_source_run_jobs,
)
from app.services.memory_service import MemoryService, deterministic_memory_id
from tests.test_long_term_memory import FakeStore


def _run(**overrides):
    values = {
        "run_id": "a" * 32,
        "thread_id": "thread-1",
        "user_id": "teacher-1",
        "plan_id": 9,
        "message": "请记住我偏好案例教学",
        "approval": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_model_metadata_has_idempotency_and_guard_constraints() -> None:
    job_constraints = {constraint.name for constraint in MemoryReflectionJob.__table__.constraints}
    guard_constraints = {constraint.name for constraint in MemoryMutationGuard.__table__.constraints}
    assert "uq_memory_reflection_job_idempotency" in job_constraints
    assert "uq_memory_mutation_guard_target" in guard_constraints
    assert {"attempts", "available_at", "lease_owner", "lease_expires_at"}.isdisjoint(
        MemoryReflectionJob.__table__.columns.keys()
    )


def test_startup_migration_is_idempotent() -> None:
    class Connection:
        def __init__(self) -> None:
            self.calls = []

        async def execute(self, statement):
            self.calls.append(statement)

    async def exercise() -> None:
        connection = Connection()
        assert await upgrade(connection) == "ready"
        assert await upgrade(connection) == "ready"
        assert len(connection.calls) == 2
        assert "CREATE TABLE IF NOT EXISTS memory_reflection_jobs" in connection.calls[0]
        assert "CREATE INDEX IF NOT EXISTS" in connection.calls[0]

    asyncio.run(exercise())
    assert {"version", "deletion_generation", "deleted_at", "last_applied_job_id"} <= set(
        MemoryMutationGuard.__table__.columns.keys()
    )


def test_config_defaults_and_environment_overrides(monkeypatch) -> None:
    monkeypatch.delenv("MEMORY_REFLECTION_WORKER_ENABLED", raising=False)
    assert config.get_memory_reflection_worker_enabled() is True
    monkeypatch.setenv("MEMORY_REFLECTION_WORKER_ENABLED", "false")
    monkeypatch.setenv("MEMORY_REFLECTION_EVALUATION_TIMEOUT_SECONDS", "12.5")
    assert config.get_memory_reflection_worker_enabled() is False
    assert config.get_memory_reflection_evaluation_timeout_seconds() == 12.5


def test_snapshot_models_bound_content_and_forbid_runtime_fields(monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_REFLECTION_PROFILE_SNAPSHOT_MAX_CHARS", "256")
    snapshot = ProfileReflectionSnapshot(
        user_id="teacher-1",
        source_run_id="run-1",
        source_thread_id="thread-1",
        business_stage="succeeded",
        captured_at=datetime.now(UTC),
        user_input="x" * 400,
    )
    assert len(snapshot.user_input) == 256
    with pytest.raises(ValidationError):
        ProfileReflectionSnapshot.model_validate(
            {
                **snapshot.model_dump(),
                "authorization": "Bearer secret",
            }
        )


def test_snapshot_builder_handles_boundaries_and_allowlists() -> None:
    assert build_reflection_job_candidates(run=_run(), status="failed", checkpoint_values={}) == []
    approval_resume = build_reflection_job_candidates(
        run=_run(approval={"interrupt_id": "i-1"}), status="waiting_approval", checkpoint_values={}
    )
    assert approval_resume == []
    paused = build_reflection_job_candidates(run=_run(), status="waiting_approval", checkpoint_values=None)
    assert [candidate.kind for candidate in paused] == ["profile"]

    completed = build_reflection_job_candidates(
        run=_run(),
        status="succeeded",
        checkpoint_values={
            "intent": "teaching_plan",
            "messages": ["must not persist" * 1000],
            "rag_context": "must not persist",
            "teaching_design_plan": "可复用的探究式教学设计",
            "teaching_metadata": {"subject": "数学", "school": "private"},
        },
    )
    assert [candidate.kind for candidate in completed] == ["profile", "experience"]
    experience = completed[-1].snapshot
    assert isinstance(experience, ExperienceReflectionSnapshot)
    assert experience.evidence_type == "generated_plan"
    assert experience.teaching_metadata == {"subject": "数学"}
    serialized = str(experience.model_dump())
    assert "rag_context" not in serialized
    assert "must not persist" not in serialized
    normal_chat = build_reflection_job_candidates(
        run=_run(),
        status="succeeded",
        checkpoint_values={
            "intent": "normal_chat",
            "teaching_design_plan": "上一轮遗留方案",
            "revision_results": [{"status": "ready", "artifact_type": "ppt"}],
        },
    )
    assert [candidate.kind for candidate in normal_chat] == ["profile"]


def test_artifact_snapshot_records_generated_and_revision_evidence() -> None:
    generated = build_reflection_job_candidates(
        run=_run(message=""),
        status="succeeded",
        checkpoint_values={
            "intent": "teaching_plan",
            "revision_results": [{"status": "ready", "artifact_type": "ppt", "title": "函数", "artifact_id": 99}],
        },
    )
    revised = build_reflection_job_candidates(
        run=_run(message=""),
        status="succeeded",
        checkpoint_values={
            "intent": "artifact_revision",
            "revision_source_artifacts": [{"id": 99}],
            "revision_results": [{"status": "ready", "artifact_type": "ppt", "title": "函数"}],
        },
    )
    assert generated[0].snapshot.evidence_type == "generated_artifact"
    assert revised[0].snapshot.evidence_type == "revised_artifact"
    assert "artifact_id" not in generated[0].snapshot.outcome_summary


def test_extractor_returns_proposal_without_store_write(monkeypatch) -> None:
    class Reflector:
        async def ainvoke(self, messages):
            _ = messages
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "create_memory",
                        "args": {"title": "风格", "content": "偏好案例教学", "tags": ["style"]},
                        "id": "call-1",
                    }
                ],
            )

    async def exercise() -> None:
        store = FakeStore()
        monkeypatch.setattr(memory_module, "profile_reflector", Reflector())
        proposal = await extract_profile_memory_proposal(
            store=store,
            snapshot=ProfileReflectionSnapshot(
                user_id="teacher-1",
                source_run_id="run-1",
                source_thread_id="thread-1",
                business_stage="succeeded",
                captured_at=datetime.now(UTC),
                user_input="请记住我偏好案例教学",
            ),
        )
        assert proposal.operation == "create"
        assert store.data.get(profile_namespace("teacher-1"), {}) == {}

    asyncio.run(exercise())


def test_graph_topology_no_longer_contains_reflection_nodes() -> None:
    source = inspect.getsource(graph.build_agent_graph)
    assert "profile_memory_reflection_node" not in source
    assert "experience_memory_reflection_node" not in source
    assert "memory_reflection_goto" not in inspect.getsource(graph)
    assert 'add_edge("profile_memory_load_node", CONVERSATION_ENTRY_NODE)' in source
    assert 'add_edge("artifact_fan_in_node", END)' in source


def test_automatic_create_id_is_stable_and_job_scoped() -> None:
    assert deterministic_memory_id("job-1") == deterministic_memory_id("job-1")
    assert deterministic_memory_id("job-1") != deterministic_memory_id("job-2")


def test_manual_edit_and_delete_make_pending_automatic_update_stale() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(MemoryMutationGuard.__table__.create)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        store = FakeStore()
        async with sessions() as db:
            service = MemoryService(db, store)
            created = await service.create_manual(
                user_id="teacher-1",
                kind="profile",
                value={"title": "风格", "content": "初始偏好", "summary": "初始偏好"},
            )
            memory_id = created["id"]
        captured_at = datetime.now(UTC)
        async with sessions() as db:
            await MemoryService(db, store).update_manual(
                user_id="teacher-1",
                kind="profile",
                memory_id=memory_id,
                value={"content": "用户手工修改", "summary": "用户手工修改"},
            )
        proposal = MemoryMutationProposal(
            operation="update",
            kind="profile",
            target_memory_id=memory_id,
            base_version=1,
            title="风格",
            content="后台旧结果",
        )
        async with sessions() as db:
            result = await MemoryService(db, store).apply_automatic(
                user_id="teacher-1",
                job_id="job-edit",
                proposal=proposal,
                source_thread_id="thread-1",
                source_plan_id=None,
                job_captured_at=captured_at,
            )
        assert result.status == "stale"
        assert store.data[profile_namespace("teacher-1")][memory_id]["content"] == "用户手工修改"

        delete_capture = datetime.now(UTC)
        async with sessions() as db:
            await MemoryService(db, store).delete_manual(user_id="teacher-1", kind="profile", memory_id=memory_id)
        async with sessions() as db:
            deleted_result = await MemoryService(db, store).apply_automatic(
                user_id="teacher-1",
                job_id="job-delete",
                proposal=proposal,
                source_thread_id="thread-1",
                source_plan_id=None,
                job_captured_at=delete_capture,
            )
        assert deleted_result.status == "stale"
        assert memory_id not in store.data[profile_namespace("teacher-1")]
        await engine.dispose()

    asyncio.run(exercise())


def test_automatic_create_replay_and_store_ack_gap_have_one_effect() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(MemoryMutationGuard.__table__.create)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        store = FakeStore()
        proposal = MemoryMutationProposal(
            operation="create", kind="experience", title="探究学习", content="先提出问题再分组验证"
        )
        for _ in range(2):
            async with sessions() as db:
                result = await MemoryService(db, store).apply_automatic(
                    user_id="teacher-1",
                    job_id="job-1",
                    proposal=proposal,
                    source_thread_id="thread-1",
                    source_plan_id=9,
                    job_captured_at=datetime.now(UTC),
                )
                assert result.status == "applied"
        namespace = ("users", "teacher-1", "experiences")
        assert list(store.data[namespace]) == [deterministic_memory_id("job-1")]
        async with sessions() as db:
            duplicate = await MemoryService(db, store).apply_automatic(
                user_id="teacher-1",
                job_id="job-2",
                proposal=proposal,
                source_thread_id="thread-2",
                source_plan_id=10,
                job_captured_at=datetime.now(UTC),
            )
            assert duplicate.status == "stale"
        assert list(store.data[namespace]) == [deterministic_memory_id("job-1")]

        ack_gap_id = deterministic_memory_id("job-gap")
        await store.aput(
            namespace,
            ack_gap_id,
            {
                "kind": "experience",
                "title": "已写入",
                "content": "一次效果",
                "_guard_version": 1,
                "_last_applied_job_id": "job-gap",
            },
        )
        async with sessions() as db:
            repaired = await MemoryService(db, store).apply_automatic(
                user_id="teacher-1",
                job_id="job-gap",
                proposal=proposal,
                source_thread_id="thread-1",
                source_plan_id=9,
                job_captured_at=datetime.now(UTC),
            )
            assert repaired.status == "applied"
        assert len(store.data[namespace]) == 2
        await engine.dispose()

    asyncio.run(exercise())


def test_production_mutation_call_sites_use_memory_service() -> None:
    from app.api import memory as memory_api
    from app.core import memory_worker

    for module in (memory_api, memory_worker, graph):
        source = inspect.getsource(module)
        assert "put_memory_item(" not in source
        assert "delete_memory_item(" not in source
        assert "apply_memory_tool_call(" not in source


def test_source_run_wait_reports_timeout_separately() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(MemoryReflectionJob.__table__.create)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        with pytest.raises(TimeoutError, match="source run missing-run"):
            await wait_for_source_run_jobs(
                sessions,
                "missing-run",
                timeout_seconds=0.01,
                poll_seconds=0.001,
            )
        await engine.dispose()

    asyncio.run(exercise())


def test_worker_has_bounded_start_stop_lifecycle(monkeypatch) -> None:
    async def exercise() -> None:
        worker = MemoryReflectionWorker(FakeStore())
        polled = asyncio.Event()

        async def run_once():
            polled.set()
            return 0

        monkeypatch.setattr(worker, "run_once", run_once)

        async def no_interrupted_jobs(repository):
            _ = repository
            return []

        monkeypatch.setattr(MemoryReflectionJobRepository, "fail_interrupted", no_interrupted_jobs)
        monkeypatch.setattr("app.core.memory_worker.get_memory_reflection_poll_seconds", lambda: 60.0)
        await worker.start()
        await asyncio.wait_for(polled.wait(), timeout=1)
        await worker.stop(timeout_seconds=1)
        assert worker._task is None

    asyncio.run(exercise())


def test_worker_startup_is_disabled_or_failure_isolated(monkeypatch) -> None:
    import app.main as main_module

    async def exercise() -> None:
        monkeypatch.setattr(main_module, "get_memory_reflection_worker_enabled", lambda: False)
        assert await main_module._start_memory_reflection_worker(FakeStore()) is None

        class FailingWorker:
            def __init__(self, store):
                _ = store

            async def start(self):
                raise RuntimeError("startup failed")

        monkeypatch.setattr(main_module, "get_memory_reflection_worker_enabled", lambda: True)
        monkeypatch.setattr(main_module, "MemoryReflectionWorker", FailingWorker)
        assert await main_module._start_memory_reflection_worker(FakeStore()) is None

    asyncio.run(exercise())


def test_memory_observations_use_bounded_labels_and_no_snapshot_fields() -> None:
    from prometheus_client import CollectorRegistry, generate_latest

    event = ObservationEvent(
        event="memory.reflection.job",
        kind="metric",
        context=RunContext(
            run_id="high-cardinality-run",
            thread_id="high-cardinality-thread",
            user_id="high-cardinality-user",
            agent_name="memory_worker",
        ),
        status="failed",
        fields={
            "job_kind": "profile",
            "job_state": "failed",
            "error_category": "model_error",
        },
    )
    assert_prometheus_labels_are_bounded(event)
    registry = CollectorRegistry()
    sink = PrometheusObservationSink(registry=registry)
    sink.emit(
        ObservationEvent(
            event="memory.reflection.failed",
            kind="log",
            context=event.context,
            status="failed",
            fields=event.fields,
        )
    )
    sink.emit(event)
    metrics = generate_latest(registry).decode("utf-8")
    assert (
        'smartclass_memory_reflection_jobs_total{error_category="model_error",job_kind="profile",job_state="failed"} 1.0'
        in metrics
    )
    assert "attempt_bucket" not in metrics
    worker_source = inspect.getsource(MemoryReflectionWorker._process)
    assert '"snapshot"' not in worker_source
    assert '"memory_content"' not in worker_source


def test_terminal_failure_interrupted_reconciliation_skip_and_cleanup(monkeypatch) -> None:
    async def exercise() -> None:
        monkeypatch.setenv("MEMORY_REFLECTION_TERMINAL_RETENTION_DAYS", "1")
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(MemoryReflectionJob.__table__.create)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        captured = datetime.now(UTC)
        snapshot = ProfileReflectionSnapshot(
            user_id="teacher-1",
            source_run_id="run-failed",
            source_thread_id="thread-1",
            business_stage="succeeded",
            captured_at=captured,
            user_input="请记住我偏好案例教学",
        )
        row = MemoryReflectionJob(
            job_id="job-failed",
            user_id="teacher-1",
            source_run_id="run-failed",
            source_thread_id="thread-1",
            kind="profile",
            business_stage="succeeded",
            extractor_version="v1",
            snapshot_version=1,
            snapshot=snapshot.model_dump(mode="json"),
            status="running",
        )
        async with sessions() as db:
            db.add(row)
            await db.commit()
            repository = MemoryReflectionJobRepository(db)
            await repository.fail("job-failed", category="model_error")
            failed = await db.get(MemoryReflectionJob, "job-failed")
            assert failed.status == JOB_FAILED
            assert failed.error_category == "model_error"
            failed.completed_at = captured.replace(year=captured.year - 1)
            await db.commit()
            assert await repository.cleanup_terminal(now=captured) == 1

            interrupted_row = MemoryReflectionJob(
                job_id="job-interrupted",
                user_id="teacher-1",
                source_run_id="run-interrupted",
                source_thread_id="thread-1",
                kind="profile",
                business_stage="succeeded",
                extractor_version="v1",
                snapshot_version=1,
                snapshot=snapshot.model_dump(mode="json"),
                status="running",
            )
            skip_row = MemoryReflectionJob(
                job_id="job-skip",
                user_id="teacher-1",
                source_run_id="run-skip",
                source_thread_id="thread-1",
                kind="profile",
                business_stage="succeeded",
                extractor_version="v1",
                snapshot_version=1,
                snapshot=snapshot.model_dump(mode="json"),
                status="running",
            )
            db.add_all([interrupted_row, skip_row])
            await db.commit()
            await repository.skip("job-skip")
            assert (await db.get(MemoryReflectionJob, "job-skip")).status == JOB_SKIPPED
            assert await repository.fail_interrupted() == ["profile"]
            interrupted = await db.get(MemoryReflectionJob, "job-interrupted")
            await db.refresh(interrupted)
            assert interrupted.status == JOB_FAILED
            assert interrupted.error_category == "worker_interrupted"
        await engine.dispose()

    asyncio.run(exercise())


def test_run_finalization_commits_terminal_state_and_jobs_idempotently() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(AgentRun.__table__.create)
            await connection.run_sync(MemoryReflectionJob.__table__.create)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        captured = datetime.now(UTC)
        snapshot = ProfileReflectionSnapshot(
            user_id="7",
            source_run_id="run-finalize",
            source_thread_id="thread-1",
            business_stage="succeeded",
            captured_at=captured,
            user_input="请记住我偏好案例教学",
        )
        candidate = ReflectionJobCandidate("profile", "succeeded", "v1", snapshot)
        async with sessions() as db:
            db.add(
                AgentRun(
                    run_id="run-finalize",
                    thread_id="thread-1",
                    user_id=7,
                    plan_id=9,
                    status="running",
                    message="请记住我偏好案例教学",
                    attachment_ids=[],
                    output_text="",
                )
            )
            await db.commit()
            finalized = await chat_run_service.finalize_chat_run(
                db,
                run_id="run-finalize",
                status="succeeded",
                output_text="done",
                last_sequence=4,
                reflection_candidates=[candidate],
            )
            assert finalized.status == "succeeded"
            assert finalized.last_event_sequence == 5
            await chat_run_service.finalize_chat_run(
                db,
                run_id="run-finalize",
                status="succeeded",
                output_text="ignored",
                last_sequence=8,
                reflection_candidates=[candidate],
            )
        async with sessions() as db:
            jobs = list((await db.execute(select(MemoryReflectionJob))).scalars().all())
            assert len(jobs) == 1
            assert (await db.get(AgentRun, "run-finalize")).output_text == "done"
        await engine.dispose()

    asyncio.run(exercise())


def test_chat_run_boundary_builds_jobs_without_waiting_for_extractor(monkeypatch) -> None:
    import app.core.chat_runs as chat_runs_module

    source_run = _run()
    source_run.status = "running"
    source_run.output_text = ""
    source_run.last_event_sequence = 0
    captured = []

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, traceback):
            _ = exc_type, exc, traceback

    class Runtime:
        values = {
            "intent": "teaching_plan",
            "revision_results": [{"status": "ready", "artifact_type": "ppt", "title": "函数"}],
        }

        async def get_memory_reflection_checkpoint_values(self, thread_id):
            _ = thread_id
            if isinstance(self.values, Exception):
                raise self.values
            return self.values

    class EventStore:
        async def get_snapshot(self, run_id):
            _ = run_id
            return None

        async def append_done(self, run_id, *, sequence, status):
            _ = run_id, sequence, status
            return True

    async def fake_get(db, run_id):
        _ = db, run_id
        return source_run

    async def fake_finalize(db, **kwargs):
        _ = db
        captured.extend(kwargs["reflection_candidates"])
        source_run.status = kwargs["status"]
        source_run.last_event_sequence = kwargs["last_sequence"] + 1
        return source_run

    class BlockingReflector:
        async def ainvoke(self, messages):
            _ = messages
            await asyncio.Event().wait()

    monkeypatch.setattr(memory_module, "profile_reflector", BlockingReflector())
    monkeypatch.setattr(chat_runs_module, "AsyncSessionLocal", SessionContext)
    monkeypatch.setattr(chat_run_service, "get_chat_run", fake_get)
    monkeypatch.setattr(chat_run_service, "finalize_chat_run", fake_finalize)

    async def exercise() -> None:
        runtime = Runtime()
        manager = ChatRunManager(runtime, EventStore())
        await asyncio.wait_for(
            manager._finalize_run(
                source_run.run_id,
                status="succeeded",
                fallback_output="done",
                fallback_sequence=3,
            ),
            timeout=0.25,
        )
        assert [candidate.kind for candidate in captured] == ["profile", "experience"]
        captured.clear()
        runtime.values = {"intent": "normal_chat", "teaching_design_plan": "old plan"}
        await asyncio.wait_for(
            manager._finalize_run(
                source_run.run_id,
                status="succeeded",
                fallback_output="chat done",
                fallback_sequence=4,
            ),
            timeout=0.25,
        )
        assert [candidate.kind for candidate in captured] == ["profile"]
        captured.clear()
        runtime.values = RuntimeError("checkpoint unavailable")
        await asyncio.wait_for(
            manager._finalize_run(
                source_run.run_id,
                status="succeeded",
                fallback_output="still done",
                fallback_sequence=6,
            ),
            timeout=0.25,
        )
        assert [candidate.kind for candidate in captured] == ["profile"]
        captured.clear()
        await asyncio.wait_for(
            manager._finalize_run(
                source_run.run_id,
                status="waiting_approval",
                fallback_output="question",
                fallback_sequence=5,
            ),
            timeout=0.25,
        )
        assert [candidate.kind for candidate in captured] == ["profile"]
        captured.clear()

        def fail_snapshot_build(**kwargs):
            _ = kwargs
            raise ValueError("invalid snapshot configuration")

        monkeypatch.setattr(chat_runs_module, "build_reflection_job_candidates", fail_snapshot_build)
        runtime.values = {"intent": "normal_chat"}
        finalized = await asyncio.wait_for(
            manager._finalize_run(
                source_run.run_id,
                status="succeeded",
                fallback_output="completed despite snapshot failure",
                fallback_sequence=7,
            ),
            timeout=0.25,
        )
        assert finalized.status == "succeeded"
        assert captured == []

    asyncio.run(exercise())


def test_memory_api_contract_routes_mutations_through_guards() -> None:
    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(MemoryMutationGuard.__table__.create)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        store = FakeStore()
        app = FastAPI()
        app.include_router(memory_router)

        async def db_override():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
        app.dependency_overrides[get_agent_runtime] = lambda: SimpleNamespace(memory_store=store)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post(
                "/memory",
                json={
                    "user_id": "spoofed",
                    "kind": "profile",
                    "title": "风格",
                    "content": "偏好案例教学",
                    "tags": ["style"],
                },
            )
            assert created.status_code == 200
            payload = created.json()["data"]
            memory_id = payload["id"]
            assert payload["kind"] == "profile"
            updated = await client.put(
                f"/memory/profile/{memory_id}",
                json={"content": "偏好探究教学"},
            )
            assert updated.status_code == 200
            assert updated.json()["data"]["content"] == "偏好探究教学"
            listed = await client.get("/memory", params={"kind": "profile"})
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()["data"]["items"]] == [memory_id]
            deleted = await client.delete(f"/memory/profile/{memory_id}")
            assert deleted.status_code == 200
        assert ("users", "spoofed", "profile") not in store.data
        async with sessions() as db:
            guard = (
                await db.execute(
                    select(MemoryMutationGuard).where(
                        MemoryMutationGuard.user_id == "7",
                        MemoryMutationGuard.kind == "profile",
                        MemoryMutationGuard.memory_id == memory_id,
                    )
                )
            ).scalar_one()
            assert guard.version == 3
            assert guard.deleted_at is not None
            assert guard.deletion_generation == 1
        await engine.dispose()

    asyncio.run(exercise())


def test_worker_processes_pending_fails_interrupted_on_startup_and_supports_shadow(monkeypatch) -> None:
    import app.core.memory_worker as worker_module

    async def exercise() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(MemoryReflectionJob.__table__.create)
            await connection.run_sync(MemoryMutationGuard.__table__.create)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(worker_module, "AsyncSessionLocal", sessions)
        store = FakeStore()

        async def extract(**kwargs):
            snapshot = kwargs["snapshot"]
            return MemoryMutationProposal(
                operation="create",
                kind="profile",
                title=f"风格-{snapshot.source_run_id}",
                content=f"偏好案例教学-{snapshot.source_run_id}",
            )

        monkeypatch.setattr(worker_module, "extract_profile_memory_proposal", extract)
        candidate = build_reflection_job_candidates(
            run=_run(run_id="run-worker"), status="succeeded", checkpoint_values={}
        )[0]
        async with sessions() as db:
            pending = (await register_reflection_candidates(db, [candidate]))[0]
            await db.commit()

        worker = MemoryReflectionWorker(store)
        assert await worker.run_once() == 1
        async with sessions() as db:
            completed = await db.get(MemoryReflectionJob, pending.job_id)
            assert completed.status == "succeeded"

            interrupted_candidate = build_reflection_job_candidates(
                run=_run(run_id="run-interrupted"), status="succeeded", checkpoint_values={}
            )[0]
            interrupted = (await register_reflection_candidates(db, [interrupted_candidate]))[0]
            interrupted.status = "running"
            continued_candidate = build_reflection_job_candidates(
                run=_run(run_id="run-pending-after-restart"), status="succeeded", checkpoint_values={}
            )[0]
            continued = (await register_reflection_candidates(db, [continued_candidate]))[0]
            await db.commit()

        restarted = MemoryReflectionWorker(store)
        polled = asyncio.Event()

        async def idle_once():
            polled.set()
            return 0

        monkeypatch.setattr(restarted, "run_once", idle_once)
        await restarted.start()
        await asyncio.wait_for(polled.wait(), timeout=1)
        await restarted.stop(timeout_seconds=1)
        async with sessions() as db:
            interrupted = await db.get(MemoryReflectionJob, interrupted.job_id)
            assert interrupted.status == "failed"
            assert interrupted.error_category == "worker_interrupted"
            assert (await db.get(MemoryReflectionJob, continued.job_id)).status == "pending"

        continuing_worker = MemoryReflectionWorker(store)
        assert await continuing_worker.run_once() == 1
        async with sessions() as db:
            assert (await db.get(MemoryReflectionJob, continued.job_id)).status == "succeeded"

            shadow_candidate = build_reflection_job_candidates(
                run=_run(run_id="run-shadow"), status="succeeded", checkpoint_values={}
            )[0]
            shadow_job = (await register_reflection_candidates(db, [shadow_candidate]))[0]
            await db.commit()
        before_count = len(store.data.get(profile_namespace("teacher-1"), {}))
        shadow = MemoryReflectionWorker(store, shadow=True)
        assert await shadow.run_once() == 1
        async with sessions() as db:
            shadow_job = await db.get(MemoryReflectionJob, shadow_job.job_id)
            assert shadow_job.status == "skipped"
            assert shadow_job.error_category == "shadow_mode"
        assert len(store.data.get(profile_namespace("teacher-1"), {})) == before_count
        await engine.dispose()

    asyncio.run(exercise())

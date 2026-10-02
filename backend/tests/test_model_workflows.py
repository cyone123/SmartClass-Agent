"""Stage 2 gates: real checkpoints/SQLite, deterministic models, no external requests."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import agent as agent_module
from app.core import graph as graph_module
from app.core import memory_worker as worker_module
from app.core.agent import AgentRuntime
from app.core.conversation_orchestration import (
    RESTART_INTAKE_TOOL,
    REVISE_ARTIFACT_TOOL,
    START_TEACHING_DESIGN_TOOL,
    SUBMIT_METADATA_TOOL,
)
from app.core.memory_retrieval import MemoryBundle
from app.core.model_access import current_snapshot, use_snapshot
from app.core.model_access import factory as factory_module
from app.core.model_access.admission import (
    admission_config,
    admission_graph,
    persist_admission,
    recover_legacy_workflow,
)
from app.core.model_access.config_repository import EnvConfigRepository
from app.core.model_access.workflow import capture_envelope, entry_update, restore_envelope
from app.migrations.v20260919_model_config_snapshot import upgrade
from app.models.agent_run import AgentRun
from app.models.memory_reflection import MemoryReflectionJob
from app.models.session import Session
from app.schemas.chat import ChatRequest
from app.schemas.memory_reflection import MemoryMutationProposal, ProfileReflectionSnapshot
from app.services import chat_run_service
from app.services.memory_reflection_service import build_reflection_job_candidates
from tests.test_model_access import environment


@pytest.fixture
def versions(monkeypatch):
    env = environment()
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    a = EnvConfigRepository(env).load()
    b = EnvConfigRepository(
        env | {"MODEL": "main-b", "STRUCTURED_MODEL": "structured-b", "SMALL_MODEL": "small-b"}
    ).load()
    monkeypatch.setattr(factory_module, "_published", a)
    return a, b


def action(name, args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "call-1"}])


@pytest.mark.asyncio
async def test_nullable_migration_is_additive_and_repeatable():
    statements = []

    class Connection:
        async def execute(self, sql):
            statements.append(sql)

    assert await upgrade(Connection()) == "ready"
    assert await upgrade(Connection()) == "ready"
    assert statements == ["ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS model_config_snapshot JSON NULL;"] * 2
    assert AgentRun.__table__.columns.model_config_snapshot.nullable


def runtime_for(graph):
    runtime = AgentRuntime.__new__(AgentRuntime)
    runtime.streaming_graph = runtime.graph = graph
    runtime._thread_locks = {}
    runtime._thread_locks_guard = asyncio.Lock()

    async def no_compression(*args, **kwargs):
        pass

    async def no_suggestions(*args, **kwargs):
        return []

    runtime._maybe_compress_thread_context = no_compression
    runtime._generate_follow_up_suggestions = no_suggestions
    return runtime


def install_graph(monkeypatch, responses, calls, branches, *, checkpointer=None):
    async def invoke(*args, **kwargs):
        calls.append(current_snapshot().fingerprint)
        return responses.pop(0)

    monkeypatch.setattr(graph_module.model_runtime, "invoke", invoke)
    monkeypatch.setattr(graph_module, "_action_model", lambda *args, **kwargs: object())

    async def memory(*args, **kwargs):
        return MemoryBundle(), {"experience_memory_scope_key": "shared", "experience_memory_context": ""}

    monkeypatch.setattr(graph_module, "_ensure_experience_snapshot", memory)

    class Rag:
        async def retrieval(self, *args, **kwargs):
            return []

    def branch(kind, key):
        async def run(state, config=None):
            await asyncio.sleep(0)
            assert config["configurable"]["run_context"].model_config_fingerprint == current_snapshot().fingerprint
            branches.append((kind, current_snapshot().fingerprint, state["model_workflow_id"]))
            return {key: {"status": "ready", "artifact_id": 1, "artifact_type": kind, "title": kind, "error": None}}

        return run

    return graph_module.build_agent_graph(
        checkpointer=checkpointer or InMemorySaver(),
        store=None,
        rag_runtime=Rag(),
        ppt_generate_node=branch("ppt", "ppt_result"),
        docx_generate_node=branch("docx", "lesson_plan_result"),
        html_generate_node=branch("html-game", "game_result"),
        ppt_revision_node=branch("ppt", "ppt_result"),
        docx_revision_node=branch("docx", "lesson_plan_result"),
        html_revision_node=branch("html-game", "game_result"),
    )


@pytest.mark.asyncio
async def test_approval_restart_parallel_branches_and_new_revision(monkeypatch, versions):
    a, b = versions
    calls, branches = [], []
    responses = [
        action(START_TEACHING_DESIGN_TOOL, {"initial_request": "Physics"}),
        AIMessage(content="Which grade?"),
        action(SUBMIT_METADATA_TOOL, {"subject": "Physics", "grade": "8", "topic": "Gravity"}),
        AIMessage(content="Plan"),
        action(REVISE_ARTIFACT_TOOL, {"request": "Update slides", "suggested_targets": ["ppt"]}),
    ]
    graph = install_graph(monkeypatch, responses, calls, branches)
    config = {"configurable": {"thread_id": "workflow", "user_id": "1"}}
    await graph.ainvoke({**entry_update(capture_envelope()), "messages": [HumanMessage(content="Physics")]}, config)
    original = await graph.aget_state(config)
    original_snapshot = json.dumps(original.values["model_config_snapshot"], sort_keys=True)
    assert original.next == (graph_module.INTERRUPT_FOR_USERINPUT_NODE,)
    monkeypatch.setattr(factory_module, "_published", b)
    graph = install_graph(monkeypatch, responses, calls, branches, checkpointer=graph.checkpointer)
    for resume, expected_next in [
        ("8th grade", graph_module.METADATA_REVIEW_INTERRUPT_NODE),
        ({"action": "approve"}, graph_module.TEACHING_PLAN_REVIEW_INTERRUPT_NODE),
        ({"action": "approve", "selected_artifact_types": ["ppt", "docx", "html-game"]}, None),
    ]:
        state = await graph.aget_state(config)
        # Round trip through the exact persisted run envelope format.
        envelope = restore_envelope(json.loads(capture_envelope(state.values).model_dump_json()))
        assert envelope.current.fingerprint == b.fingerprint
        assert envelope.selected().fingerprint == a.fingerprint
        await graph.ainvoke(Command(resume=resume, update=entry_update(envelope)), config)
        state = await graph.aget_state(config)
        assert state.next == ((expected_next,) if expected_next else ())
        assert json.dumps(state.values["model_config_snapshot"], sort_keys=True) == original_snapshot
    assert calls == [a.fingerprint] * 4
    assert len(branches) == 3 and {row[1] for row in branches} == {a.fingerprint}
    assert len({row[2] for row in branches}) == 1
    assert not state.values["model_workflow_active"]
    envelope = capture_envelope(state.values)
    assert envelope.selected().fingerprint == b.fingerprint
    revised = await graph.ainvoke(
        {
            **entry_update(envelope),
            "messages": [HumanMessage(content="Update slides")],
            "artifact_catalog": [{"id": 1, "type": "ppt", "title": "Slides"}],
        },
        config,
    )
    assert calls[-1] == b.fingerprint and branches[-1][1] == b.fingerprint
    assert revised["model_workflow_id"] != original.values["model_workflow_id"]


@pytest.mark.asyncio
async def test_same_run_restart_selects_acceptance_snapshot_not_later_global(monkeypatch, versions):
    a, b = versions
    calls, branches = [], []
    responses = [
        action(START_TEACHING_DESIGN_TOOL, {"initial_request": "Physics"}),
        AIMessage(content="Which grade?"),
        action(RESTART_INTAKE_TOOL, {"initial_request": "Chemistry"}),
        AIMessage(content="Which chemistry topic?"),
    ]
    graph = install_graph(monkeypatch, responses, calls, branches)
    config = {"configurable": {"thread_id": "restart", "user_id": "1"}}
    await graph.ainvoke({**entry_update(capture_envelope()), "messages": [HumanMessage(content="Physics")]}, config)
    old = await graph.aget_state(config)
    monkeypatch.setattr(factory_module, "_published", b)
    accepted = capture_envelope(old.values)
    monkeypatch.setattr(factory_module, "_published", a)  # Changed again after acceptance.
    await graph.ainvoke(Command(resume="Switch to chemistry", update=entry_update(accepted)), config)
    state = await graph.aget_state(config)
    assert calls == [a.fingerprint, a.fingerprint, a.fingerprint, b.fingerprint]
    assert state.values["model_config_selection"] == "accepted_current"
    assert state.values["model_workflow_id"] != old.values["model_workflow_id"]
    assert accepted.workflow.fingerprint == a.fingerprint
    assert accepted.current.fingerprint == b.fingerprint
    await graph.ainvoke(Command(resume="取消本次教学设计"), config)
    assert not (await graph.aget_state(config)).values["model_workflow_active"]


@pytest.mark.asyncio
async def test_legacy_run_adopts_once_and_public_request_cannot_supply_snapshot(versions):
    a, b = versions
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(AgentRun.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        run = AgentRun(
            run_id="old", thread_id="t", user_id=1, plan_id=1, status="queued", message="hi", attachment_ids=[]
        )
        db.add(run)
        await db.commit()
        assert run.model_config_snapshot is None
        adopted = await chat_run_service.adopt_model_snapshot(db, run, {"teaching_task_active": True})
        assert adopted["legacy_snapshot_adopted"] is True
    with use_snapshot(b):
        async with sessions() as db:
            stored = await db.get(AgentRun, "old")
            assert await chat_run_service.adopt_model_snapshot(db, stored) == adopted
            assert "model_config_snapshot" not in chat_run_service.serialize_chat_run(stored)
    request = ChatRequest.model_validate({"message": "hi", "model_config_snapshot": adopted, "model_envelope": adopted})
    assert "model_config_snapshot" not in request.model_dump() and "model_envelope" not in request.model_dump()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admission_is_durable_without_advancing_legacy_interrupt(monkeypatch, versions):
    a, b = versions
    calls, branches = [], []
    graph = install_graph(monkeypatch, [AIMessage(content="Which grade?")], calls, branches)
    config = {"configurable": {"thread_id": "legacy-pause", "user_id": "1"}}
    # Seed a legacy checkpoint at a real interrupt, without model configuration fields.
    await graph.aupdate_state(
        config,
        {"messages": [HumanMessage(content="Physics")], "teaching_task_active": True},
        as_node=graph_module.INTERRUPT_FOR_USERINPUT_NODE,
    )
    await graph.ainvoke(None, config)
    before = await graph.aget_state(config)
    assert before.interrupts
    sidecar = admission_graph(graph.checkpointer)
    values = {**before.values, "model_workflow_active": True}
    adopted = await persist_admission(sidecar, "legacy-pause", "run-1", values)
    after = await graph.aget_state(config)
    assert after.next == before.next and after.interrupts == before.interrupts
    assert len(calls) == 1  # Admission itself never contacts a model.
    assert adopted.legacy_snapshot_adopted and adopted.selected().fingerprint == a.fingerprint
    assert (await sidecar.aget_state(admission_config("legacy-pause"))).values["envelope"]
    monkeypatch.setattr(factory_module, "_published", b)
    # Rebuild the metadata graph to simulate a process using existing persisted storage.
    restarted = admission_graph(graph.checkpointer)
    same_run = await persist_admission(restarted, "legacy-pause", "run-1", values)
    assert same_run == adopted
    recovered = await recover_legacy_workflow(restarted, "legacy-pause", values)
    next_run = await persist_admission(restarted, "legacy-pause", "run-2", recovered)
    assert next_run.selected().fingerprint == a.fingerprint and next_run.current.fingerprint == b.fingerprint


@pytest.mark.asyncio
async def test_new_run_acceptance_commits_server_snapshot(versions):
    a, _ = versions
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Session.__table__.create)
        await connection.run_sync(AgentRun.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add(Session(thread_id="t", user_id=1, plan_id=1, name="test"))
        await db.commit()
        run = await chat_run_service.create_chat_run(
            db, thread_id="t", user_id=1, plan_id=1, message="hi", attachment_ids=[], approval=None
        )
    async with sessions() as db:
        stored = await db.get(AgentRun, run.run_id)
        assert stored.status == "queued"
        assert restore_envelope(stored.model_config_snapshot).selected().fingerprint == a.fingerprint
    await engine.dispose()


@pytest.mark.asyncio
async def test_restart_between_acceptance_and_graph_write_retains_legacy_identity(monkeypatch, versions):
    a, b = versions
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Session.__table__.create)
        await connection.run_sync(AgentRun.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add(Session(thread_id="legacy-gap", user_id=1, plan_id=1, name="test"))
        await db.commit()
        run = await chat_run_service.create_chat_run(
            db,
            thread_id="legacy-gap",
            user_id=1,
            plan_id=1,
            message="",
            attachment_ids=[],
            approval={"action": "approve"},
            workflow_state={"model_workflow_active": True},
        )
        run.status = "failed"  # Existing startup reconciliation policy.
        await db.commit()
    monkeypatch.setattr(factory_module, "_published", b)
    async with sessions() as db:
        recovered = await chat_run_service.create_chat_run(
            db,
            thread_id="legacy-gap",
            user_id=1,
            plan_id=1,
            message="",
            attachment_ids=[],
            approval={"action": "approve"},
            workflow_state={"model_workflow_active": True},
        )
        envelope = restore_envelope(recovered.model_config_snapshot)
        assert envelope.selected().fingerprint == a.fingerprint
        assert envelope.current.fingerprint == b.fingerprint
        assert envelope.legacy_snapshot_adopted
    await engine.dispose()


@pytest.mark.asyncio
async def test_database_adoption_failure_never_returns_executable_snapshot(versions):
    class FailingDB:
        async def commit(self):
            raise RuntimeError("commit failed")

    run = AgentRun(run_id="legacy", model_config_snapshot=None)
    with pytest.raises(RuntimeError, match="commit failed"):
        await chat_run_service.adopt_model_snapshot(FailingDB(), run)
    assert run.model_config_snapshot is None


@pytest.mark.asyncio
async def test_concurrent_role_contexts_and_agent_bindings_do_not_cross(monkeypatch, versions):
    a, b = versions
    models, creations = [], []

    class Model:
        def __init__(self, role):
            self.role = role
            self.identity = current_snapshot().fingerprint

    def model(streaming=False):
        resolved = Model("main")
        models.append(resolved)
        return resolved

    def create(**kwargs):
        creations.append(kwargs)
        return kwargs["model"]

    monkeypatch.setattr(agent_module, "get_model", model)
    monkeypatch.setattr(agent_module, "create_agent", create)
    runtime = AgentRuntime.__new__(AgentRuntime)
    runtime.base_middleware = []
    runtime.skill_toolset = SimpleNamespace(tools=[])
    runtime.workspace_toolset = SimpleNamespace(tools=[])
    runtime.experience_search_tool = object()

    async def branch(snapshot, kind):
        with use_snapshot(snapshot):
            await asyncio.sleep(0)
            result = runtime._artifact_agent(kind)
            await asyncio.sleep(0)
            assert current_snapshot().fingerprint == snapshot.fingerprint
            return result

    results = await asyncio.gather(branch(a, "ppt"), branch(b, "docx"))
    assert [model.identity for model in results] == [a.fingerprint, b.fingerprint]
    assert creations[0]["tools"] is not creations[1]["tools"]
    assert creations[0]["name"] != creations[1]["name"]


@pytest.mark.asyncio
async def test_compression_uses_checkpoint_role_and_init_failure_preserves_history(monkeypatch, versions):
    from app.core import context_compression as compression
    from app.core.observability import RunContext
    from tests.test_context_compression import FakeCompressionModel, MemorySink, _settings, _thread_messages

    a, b = versions
    identities = []

    def configured(streaming=False):
        identities.append(current_snapshot().fingerprint)
        return FakeCompressionModel()

    monkeypatch.setattr(compression, "get_context_compression_llm", configured)
    state = {"messages": _thread_messages(), "model_config_snapshot": a.model_dump(mode="json")}
    before = list(state["messages"])
    with use_snapshot(b):
        result = await compression.compress_state_messages(
            state, context=RunContext(run_id="c"), sink=MemorySink(), settings=_settings()
        )
    assert identities == [a.fingerprint] and result.status == "success"

    def unavailable(streaming=False):
        raise RuntimeError("model initialization failed")

    monkeypatch.setattr(compression, "get_context_compression_llm", unavailable)
    result = await compression.compress_state_messages(
        state, context=RunContext(run_id="c"), sink=MemorySink(), settings=_settings()
    )
    assert result.status == "failed" and result.update is None and state["messages"] == before


@pytest.mark.asyncio
async def test_checkpoint_persistence_failure_prevents_attachments_and_models(versions):
    calls = []

    class Graph:
        async def aget_state(self, config):
            return SimpleNamespace(values={"teaching_task_active": True}, interrupts=(), next=())

        async def aupdate_state(self, config, update):
            raise RuntimeError("persistence failed")

        async def astream(self, *args, **kwargs):
            calls.append("model")
            yield {}

    runtime = runtime_for(Graph())

    async def fail_admission(*args):
        raise RuntimeError("persistence failed")

    runtime._persist_model_envelope = fail_admission

    async def attachment(*args, **kwargs):
        calls.append("attachment")

    runtime.build_attachment_text = attachment
    events = [event async for event in runtime.stream_agent_events("hi", "t", run_id="r", attachments=[object()])]
    assert calls == [] and [event["event"] for event in events] == ["error"]


@pytest.mark.asyncio
async def test_runtime_stream_admission_precedes_attachments_and_preserves_approval(monkeypatch, versions):
    a, b = versions
    responses = [
        action(START_TEACHING_DESIGN_TOOL, {"initial_request": "Physics"}),
        action(SUBMIT_METADATA_TOOL, {"subject": "Physics", "grade": "8", "topic": "Gravity"}),
        AIMessage(content="Plan"),
    ]
    calls, branches = [], []
    graph = install_graph(monkeypatch, responses, calls, branches)
    runtime = runtime_for(graph)

    class DB:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    async def artifacts(*args, **kwargs):
        return []

    monkeypatch.setattr(agent_module, "AsyncSessionLocal", DB)
    monkeypatch.setattr(agent_module.artifact_service, "list_latest_ready_current_artifacts_by_thread", artifacts)
    attached = []

    async def attachment(*args, **kwargs):
        saved = await runtime._admission_graph().aget_state(admission_config("stream"))
        assert saved.values["run_id"] == "first"
        attached.append(current_snapshot().fingerprint)
        return "material"

    runtime.build_attachment_text = attachment
    first = [
        event
        async for event in runtime.stream_agent_events(
            "Physics", "stream", run_id="first", attachments=[SimpleNamespace(storage_path="unused")]
        )
    ]
    assert not [event for event in first if event["event"] == "error"]
    approval = next(event["data"] for event in first if event["event"] == "approval")
    assert attached == [a.fingerprint]
    monkeypatch.setattr(factory_module, "_published", b)
    await runtime.validate_approval_request("stream", approval["interrupt_id"])
    envelope = capture_envelope(await runtime.get_memory_reflection_checkpoint_values("stream"))
    second = [
        event
        async for event in runtime.stream_agent_events(
            "",
            "stream",
            run_id="second",
            model_envelope=envelope.model_dump(mode="json"),
            approval={"action": "approve", "interrupt_id": approval["interrupt_id"]},
        )
    ]
    assert not [event for event in second if event["event"] == "error"]
    assert any(event["event"] == "approval" and event["data"]["stage"] == "teaching_plan_review" for event in second)
    assert calls == [a.fingerprint] * 3
    await runtime.cancel_model_workflow("stream")
    cancelled = await graph.aget_state({"configurable": {"thread_id": "stream"}})
    assert not cancelled.next and not cancelled.values["model_workflow_active"]
    assert capture_envelope(cancelled.values).selected().fingerprint == b.fingerprint


@pytest.mark.asyncio
async def test_reflection_enqueue_identity_legacy_adoption_and_missing_key(monkeypatch, versions):
    a, b = versions
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(MemoryReflectionJob.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(worker_module, "AsyncSessionLocal", sessions)
    candidate = build_reflection_job_candidates(
        run=SimpleNamespace(run_id="r", thread_id="t", user_id=1, message="remember this", approval=None),
        status="succeeded",
        checkpoint_values={},
    )[0]
    assert candidate.snapshot.model_config_snapshot.fingerprint == a.fingerprint
    calls = []

    async def extract(**kwargs):
        calls.append(current_snapshot().fingerprint)
        # Verify durable adoption from a separate session before the fake model executes.
        async with sessions() as db:
            persisted = await db.get(MemoryReflectionJob, kwargs["snapshot"].source_run_id)
            assert persisted.snapshot["model_config_snapshot"]["fingerprint"] == calls[-1]
        return MemoryMutationProposal(operation="noop", kind="profile")

    monkeypatch.setattr(worker_module, "extract_profile_memory_proposal", extract)
    worker = worker_module.MemoryReflectionWorker(None)

    async def row(name, model_snapshot):
        snapshot = ProfileReflectionSnapshot(
            user_id="1",
            source_run_id=name,
            source_thread_id="t",
            business_stage="succeeded",
            captured_at=datetime.now(UTC),
            user_input="remember this",
            model_config_snapshot=model_snapshot,
        )
        job = MemoryReflectionJob(
            job_id=name,
            user_id="1",
            source_run_id=name,
            source_thread_id="t",
            kind="profile",
            business_stage="succeeded",
            extractor_version="v1",
            snapshot_version=2 if model_snapshot else 1,
            snapshot=snapshot.model_dump(mode="json"),
            status="running",
        )
        async with sessions() as db:
            db.add(job)
            await db.commit()
        return job

    fixed = await row("fixed", candidate.snapshot.model_config_snapshot)
    legacy = await row("legacy", None)
    monkeypatch.setattr(factory_module, "_published", b)
    await worker._process(fixed)
    await worker._process(legacy)
    assert calls == [a.fingerprint, b.fingerprint]
    assert legacy.snapshot["legacy_snapshot_adopted"] is True
    monkeypatch.setattr(factory_module, "_published", a)
    await worker._process(legacy)
    assert calls[-1] == b.fingerprint
    missing = await row("missing", a)
    monkeypatch.delenv("STRUCTURED_API_KEY")
    await worker._process(missing)
    assert len(calls) == 3
    async with sessions() as db:
        assert (await db.get(MemoryReflectionJob, "missing")).status == "failed"
    await engine.dispose()

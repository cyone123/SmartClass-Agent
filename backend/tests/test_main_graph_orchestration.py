from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END
from langgraph.types import Command

from app.core import graph as graph_module
from app.core.conversation_orchestration import (
    RESTART_INTAKE_TOOL,
    REVISE_ARTIFACT_TOOL,
    SEARCH_EXPERIENCE_TOOL,
    START_TEACHING_DESIGN_TOOL,
    SUBMIT_METADATA_TOOL,
)
from app.core.memory_retrieval import MemoryBundle


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "node_name,model_name",
    [
        ("conversation_entry_agent", "conversation_entry_runnable"),
        ("teaching_intake_agent", "teaching_intake_runnable"),
    ],
)
async def test_visible_text_arrives_before_model_finishes(monkeypatch, node_name, model_name) -> None:
    release = asyncio.Event()
    tokens = asyncio.Queue()
    config = {"configurable": {"root_text_event_emitter": tokens.put_nowait}}

    class Model:
        async def astream(self, messages, config=None):
            assert config["configurable"]["root_text_event_emitter"] == tokens.put_nowait
            yield AIMessageChunk(content="Which ")
            await release.wait()
            yield AIMessageChunk(content="grade?")

    monkeypatch.setattr(graph_module, model_name, Model())
    task = asyncio.create_task(
        getattr(graph_module, node_name)(
            {"messages": [HumanMessage(content="Help")], "teaching_intake_turn_count": 100},
            config=config,
        )
    )
    try:
        assert await asyncio.wait_for(tokens.get(), 2) == "Which "
        assert not task.done()
    finally:
        release.set()
    result = await asyncio.wait_for(task, 2)
    assert tokens.get_nowait() == "grade?"
    assert tokens.empty()  # No full-message replay at completion.
    assert result.update["messages"][0].content == "Which grade?"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "node_name,model_name,tool,args,target",
    [
        (
            "conversation_entry_agent",
            "conversation_entry_runnable",
            START_TEACHING_DESIGN_TOOL,
            {"initial_request": "Gravity lesson"},
            graph_module.TEACHING_INTAKE_NODE,
        ),
        (
            "teaching_intake_agent",
            "teaching_intake_runnable",
            SUBMIT_METADATA_TOOL,
            {"subject": "Physics", "grade": "8", "topic": "Gravity"},
            graph_module.METADATA_REVIEW_INTERRUPT_NODE,
        ),
    ],
)
async def test_streamed_narration_then_tool_routes_and_persists_text(
    monkeypatch, node_name, model_name, tool, args, target
) -> None:
    import json

    tokens = []

    class Model:
        async def astream(self, messages, config=None):
            yield AIMessageChunk(content=[{"type": "reasoning", "reasoning": "private"}])
            yield AIMessageChunk(content="Let me help.")
            arguments = json.dumps(args)
            yield AIMessageChunk(
                content="", tool_call_chunks=[{"name": tool, "args": arguments[:5], "id": "call-1", "index": 0}]
            )
            yield AIMessageChunk(
                content="", tool_call_chunks=[{"name": None, "args": arguments[5:], "id": None, "index": 0}]
            )

    monkeypatch.setattr(graph_module, model_name, Model())
    result = await getattr(graph_module, node_name)(
        {"messages": [HumanMessage(content="Help")]},
        config={"configurable": {"root_text_event_emitter": tokens.append}},
    )
    assert tokens == ["Let me help."]
    assert result.goto == target
    persisted = result.update["messages"][0]
    assert graph_module._message_to_text(persisted) == "Let me help."
    assert persisted.content[0] == {"type": "reasoning", "reasoning": "private"}
    assert persisted.tool_calls[0]["id"] == result.update["messages"][1].tool_call_id


@pytest.mark.asyncio
@pytest.mark.parametrize("already_visible", [False, True])
async def test_stream_failure_retries_only_before_visible_text(monkeypatch, already_visible) -> None:
    tokens = []
    fallback_calls = []

    class Primary:
        async def astream(self, messages, config=None):
            if already_visible:
                yield AIMessageChunk(content="Partial")
            raise RuntimeError("connection lost")

    class Fallback:
        async def astream(self, messages, config=None):
            fallback_calls.append(True)
            yield AIMessageChunk(content="Fallback ")
            yield AIMessageChunk(content="answer")

    monkeypatch.setattr(graph_module, "conversation_entry_runnable", Primary())
    monkeypatch.setattr(graph_module, "conversation_entry_fallback_runnable", Fallback())
    monkeypatch.setattr(graph_module, "is_structured_fallback_enabled", lambda: True)
    call = graph_module.conversation_entry_agent(
        {"messages": [HumanMessage(content="Help")]},
        config={"configurable": {"root_text_event_emitter": tokens.append}},
    )
    if already_visible:
        with pytest.raises(RuntimeError, match="streaming began"):
            await call
        assert tokens == ["Partial"]
        assert fallback_calls == []
    else:
        result = await call
        assert tokens == ["Fallback ", "answer"]
        assert result.update["messages"][0].content == "Fallback answer"
        assert fallback_calls == [True]


def _tool_message(name: str, args: dict, call_id: str = "call-1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _install_model_responses(monkeypatch, responses: list[AIMessage]) -> list[dict]:
    calls: list[dict] = []

    async def invoke(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return responses.pop(0)

    monkeypatch.setattr(graph_module.model_runtime, "invoke", invoke)
    return calls


@pytest.mark.asyncio
async def test_conversation_entry_answers_directly_in_one_call(monkeypatch) -> None:
    calls = _install_model_responses(monkeypatch, [AIMessage(content="Direct answer")])
    result = await graph_module.conversation_entry_agent({"messages": [HumanMessage(content="hello")]})
    assert result.goto == END
    assert result.update["messages"][0].content == "Direct answer"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_conversation_entry_starts_teaching_scope(monkeypatch) -> None:
    _install_model_responses(
        monkeypatch,
        [_tool_message(START_TEACHING_DESIGN_TOOL, {"initial_request": "Design a physics lesson"})],
    )
    state = {"messages": [HumanMessage(content="Design a physics lesson")]}
    result = await graph_module.conversation_entry_agent(state)
    assert result.goto == graph_module.TEACHING_INTAKE_NODE
    assert result.update["teaching_task_active"] is True
    assert result.update["teaching_metadata"] is None


@pytest.mark.asyncio
async def test_conversation_entry_preserves_artifact_revision_route(monkeypatch) -> None:
    _install_model_responses(
        monkeypatch,
        [_tool_message(REVISE_ARTIFACT_TOOL, {"request": "Update the PPT", "suggested_targets": ["ppt"]})],
    )
    result = await graph_module.conversation_entry_agent(
        {
            "messages": [HumanMessage(content="Update the PPT")],
            "artifact_catalog": [{"type": "ppt", "title": "Lesson"}],
        }
    )
    assert result.goto == "artifact_revision_router_node"
    assert result.update["user_feedback"] == "Update the PPT"
    assert result.update["revision_target_hints"] == ["ppt"]


def test_revision_router_uses_validated_entry_target_hints() -> None:
    result = graph_module.artifact_revision_router_node(
        {
            "messages": [HumanMessage(content="Make it shorter")],
            "revision_target_hints": ["docx"],
            "artifact_catalog": [
                {"id": 1, "type": "ppt", "title": "Slides"},
                {"id": 2, "type": "docx", "title": "Lesson plan"},
            ],
        }
    )
    assert result.goto == graph_module.ARTIFACT_REVISION_PREPARE_NODE
    assert result.update["feedback_type"] == "modify_lesson_plan"
    assert [item["id"] for item in result.update["revision_source_artifacts"]] == [2]


@pytest.mark.asyncio
async def test_entry_invalid_primary_uses_one_fallback(monkeypatch) -> None:
    calls = _install_model_responses(
        monkeypatch,
        [AIMessage(content=""), AIMessage(content="Fallback answer")],
    )
    result = await graph_module.conversation_entry_agent({"messages": [HumanMessage(content="hello")]})
    assert result.goto == END
    assert result.update["messages"][0].content == "Fallback answer"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_entry_memory_search_is_bounded_to_the_turn(monkeypatch) -> None:
    calls = _install_model_responses(
        monkeypatch,
        [
            _tool_message(SEARCH_EXPERIENCE_TOOL, {"query": "discussion strategy"}),
            AIMessage(content="Memory-assisted answer"),
        ],
    )
    memory_requests = []

    async def resolve_memory(context, request, memory_bundle=None):
        memory_requests.append(request)
        return MemoryBundle(context="Reusable experience", selected_ids=("exp-1",), selected_count=1)

    monkeypatch.setattr(graph_module.model_runtime, "resolve_memory", resolve_memory)
    result = await graph_module.conversation_entry_agent(
        {"messages": [HumanMessage(content="How should I organize a classroom discussion?")]}
    )
    assert result.goto == END
    assert result.update["messages"][-1].content == "Memory-assisted answer"
    assert result.update["messages"][0].tool_calls[0]["id"] == result.update["messages"][1].tool_call_id
    assert not any(key.startswith("experience_memory_") for key in result.update)
    assert len(memory_requests) == 1
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_intake_question_does_not_materialize_partial_metadata(monkeypatch) -> None:
    _install_model_responses(monkeypatch, [AIMessage(content="Which grade are you teaching?")])
    state = {
        "messages": [HumanMessage(content="Design a lesson about gravity")],
        "teaching_task_initial_request": "Design a lesson about gravity",
        "teaching_task_start_message_index": 0,
        "teaching_task_active": True,
    }
    result = await graph_module.teaching_intake_agent(state)
    assert result.goto == graph_module.INTERRUPT_FOR_USERINPUT_NODE
    assert "teaching_metadata" not in result.update
    assert result.update["messages"][0].content == "Which grade are you teaching?"


@pytest.mark.asyncio
async def test_intake_materializes_only_valid_final_metadata(monkeypatch) -> None:
    _install_model_responses(
        monkeypatch,
        [
            _tool_message(
                SUBMIT_METADATA_TOOL,
                {"subject": "Physics", "grade": "Grade 8", "topic": "Gravity", "course_duration": "45 min"},
            )
        ],
    )
    state = {
        "messages": [HumanMessage(content="Design a Grade 8 physics lesson about gravity for 45 minutes")],
        "teaching_task_initial_request": "Design a Grade 8 physics lesson about gravity for 45 minutes",
        "teaching_task_start_message_index": 0,
        "teaching_task_active": True,
    }
    result = await graph_module.teaching_intake_agent(state)
    assert result.goto == graph_module.METADATA_REVIEW_INTERRUPT_NODE
    assert result.update["teaching_metadata"]["is_complete"] is True
    assert result.update["last_submitted_teaching_metadata"]["topic"] == "Gravity"
    assert result.update["teaching_task_active"] is False


@pytest.mark.asyncio
async def test_intake_explicit_cancel_skips_model(monkeypatch) -> None:
    calls = _install_model_responses(monkeypatch, [])
    result = await graph_module.teaching_intake_agent(
        {
            "messages": [HumanMessage(content="\u53d6\u6d88\u672c\u6b21\u6559\u5b66\u8bbe\u8ba1")],
            "teaching_task_active": True,
        }
    )
    assert result.goto == END
    assert result.update["teaching_task_active"] is False
    assert calls == []


@pytest.mark.asyncio
async def test_intake_can_replace_the_active_task(monkeypatch) -> None:
    _install_model_responses(
        monkeypatch,
        [_tool_message(RESTART_INTAKE_TOOL, {"initial_request": "Design a chemistry lesson"})],
    )
    state = {
        "messages": [HumanMessage(content="Design physics"), HumanMessage(content="Use chemistry instead")],
        "teaching_task_initial_request": "Design physics",
        "teaching_task_start_message_index": 0,
        "teaching_task_active": True,
    }
    result = await graph_module.teaching_intake_agent(state)
    assert result.goto == graph_module.TEACHING_INTAKE_NODE
    assert result.update["teaching_task_initial_request"] == "Design a chemistry lesson"
    assert result.update["teaching_task_start_message_index"] == 1
    assert result.update["teaching_metadata"] is None


def _build_graph(*, rag_runtime=None):
    class EmptyRag:
        async def retrieval(self, *args, **kwargs):
            return []

    async def artifact_node(state, config=None):
        return {}

    return graph_module.build_agent_graph(
        checkpointer=False,
        store=None,
        rag_runtime=rag_runtime or EmptyRag(),
        ppt_generate_node=artifact_node,
        docx_generate_node=artifact_node,
        html_generate_node=artifact_node,
        ppt_revision_node=artifact_node,
        docx_revision_node=artifact_node,
        html_revision_node=artifact_node,
    )


def test_graph_contains_only_current_main_topology() -> None:
    graph = _build_graph().get_graph()
    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("profile_memory_load_node", graph_module.CONVERSATION_ENTRY_NODE) in edges
    assert (graph_module.INTERRUPT_FOR_USERINPUT_NODE, graph_module.TEACHING_INTAKE_NODE) in edges
    assert {
        "intent_router_node",
        "normal_chat_node",
        "metadata_structer_node",
        "follow_up_questioner",
    }.isdisjoint(graph.nodes)


@pytest.mark.asyncio
async def test_context_preparation_runs_rag_and_experience_concurrently(monkeypatch) -> None:
    rag_started = asyncio.Event()
    memory_started = asyncio.Event()

    class CoordinatedRag:
        async def retrieval(self, *args, **kwargs):
            rag_started.set()
            await asyncio.wait_for(memory_started.wait(), timeout=1)
            return []

    async def ensure_experience(*args, **kwargs):
        memory_started.set()
        await asyncio.wait_for(rag_started.wait(), timeout=1)
        return MemoryBundle(context="shared"), {
            "experience_memory_scope_key": "scope",
            "experience_memory_context": "shared",
            "experience_memory_selected_ids": [],
            "experience_memory_strategy": "semantic",
        }

    monkeypatch.setattr(graph_module, "_ensure_experience_snapshot", ensure_experience)
    compiled = _build_graph(rag_runtime=CoordinatedRag())
    node = compiled.nodes[graph_module.TEACHING_CONTEXT_PREPARE_NODE]
    result = await node.bound.afunc(
        {
            "messages": [HumanMessage(content="Design")],
            "teaching_metadata": {"subject": "Physics", "grade": "8", "topic": "Gravity"},
        },
        None,
        runtime=None,
    )
    assert rag_started.is_set() and memory_started.is_set()
    assert result["rag_context"] == ""
    assert result["experience_memory_context"] == "shared"


@pytest.mark.asyncio
async def test_context_preparation_degrades_rag_and_experience_independently(monkeypatch) -> None:
    class FailingRag:
        async def retrieval(self, *args, **kwargs):
            raise RuntimeError("rag unavailable")

    async def failing_experience(*args, **kwargs):
        raise RuntimeError("memory unavailable")

    monkeypatch.setattr(graph_module, "_ensure_experience_snapshot", failing_experience)
    compiled = _build_graph(rag_runtime=FailingRag())
    node = compiled.nodes[graph_module.TEACHING_CONTEXT_PREPARE_NODE]
    result = await node.bound.afunc(
        {
            "messages": [HumanMessage(content="Design")],
            "teaching_metadata": {"subject": "Physics", "grade": "8", "topic": "Gravity"},
        },
        None,
        runtime=None,
    )
    assert result["rag_context"] == ""
    assert result["rag_results"] == []
    assert result["experience_memory_context"] == ""
    assert result["experience_memory_degraded"] is True
    assert result["experience_memory_degradation_reason"] == "provider_error"


@pytest.mark.asyncio
async def test_teaching_planner_reuses_prepared_snapshot(monkeypatch) -> None:
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("snapshot must not be resolved again")

    async def invoke(*args, **kwargs):
        assert kwargs["memory_bundle"].context == "shared"
        return AIMessage(content="Plan")

    monkeypatch.setattr(graph_module, "_ensure_experience_snapshot", fail_if_called)
    monkeypatch.setattr(graph_module.model_runtime, "invoke", invoke)
    result = await graph_module.teaching_design_planner(
        {
            "messages": [HumanMessage(content="Design")],
            "teaching_metadata": {"subject": "Physics", "grade": "8", "topic": "Gravity"},
            "experience_memory_scope_key": "scope",
            "experience_memory_context": "shared",
            "experience_memory_selected_ids": ["exp-1"],
            "experience_memory_strategy": "semantic",
        },
        runtime=SimpleNamespace(context={}, store=None),
    )
    assert result["teaching_design_plan"] == "Plan"


@pytest.mark.asyncio
async def test_main_graph_smoke_covers_clarification_approvals_generation_and_revision(monkeypatch) -> None:
    responses = [
        _tool_message(START_TEACHING_DESIGN_TOOL, {"initial_request": "Design a gravity lesson"}),
        AIMessage(content="Which grade and duration?"),
        _tool_message(
            SUBMIT_METADATA_TOOL,
            {"subject": "Physics", "grade": "8", "topic": "Gravity", "course_duration": "45 min"},
        ),
        AIMessage(content="Approved teaching plan"),
        _tool_message(REVISE_ARTIFACT_TOOL, {"request": "Update the PPT", "suggested_targets": ["ppt"]}),
    ]
    _install_model_responses(monkeypatch, responses)

    async def ensure_experience(*args, **kwargs):
        return MemoryBundle(context="shared"), {
            "experience_memory_scope_key": "scope",
            "experience_memory_context": "shared",
            "experience_memory_selected_ids": [],
            "experience_memory_strategy": "semantic",
        }

    monkeypatch.setattr(graph_module, "_ensure_experience_snapshot", ensure_experience)

    class EmptyRag:
        async def retrieval(self, *args, **kwargs):
            return []

    async def ppt_generate(state, config=None):
        return {
            "ppt_result": {
                "status": "ready",
                "artifact_id": 101,
                "artifact_type": "ppt",
                "title": "Slides",
                "error": None,
            }
        }

    async def ppt_revision(state, config=None):
        return {
            "ppt_result": {
                "status": "ready",
                "artifact_id": 102,
                "artifact_type": "ppt",
                "title": "Revised slides",
                "error": None,
            }
        }

    async def unused_artifact(state, config=None):
        raise AssertionError("unselected artifact branch must not run")

    compiled = graph_module.build_agent_graph(
        checkpointer=InMemorySaver(),
        store=None,
        rag_runtime=EmptyRag(),
        ppt_generate_node=ppt_generate,
        docx_generate_node=unused_artifact,
        html_generate_node=unused_artifact,
        ppt_revision_node=ppt_revision,
        docx_revision_node=unused_artifact,
        html_revision_node=unused_artifact,
    )
    config = {"configurable": {"thread_id": "main-graph-smoke", "user_id": "1"}}

    first = await compiled.ainvoke(
        {"messages": [HumanMessage(content="Design a gravity lesson")]},
        config=config,
        context={"user_id": "1"},
    )
    assert first["teaching_metadata"] is None
    assert (await compiled.aget_state(config)).next == (graph_module.INTERRUPT_FOR_USERINPUT_NODE,)

    await compiled.ainvoke(Command(resume="Grade 8 physics, 45 minutes"), config=config, context={"user_id": "1"})
    snapshot = await compiled.aget_state(config)
    assert snapshot.next == (graph_module.METADATA_REVIEW_INTERRUPT_NODE,)
    assert snapshot.values["teaching_metadata"]["is_complete"] is True

    await compiled.ainvoke(Command(resume={"action": "approve"}), config=config, context={"user_id": "1"})
    assert (await compiled.aget_state(config)).next == (graph_module.TEACHING_PLAN_REVIEW_INTERRUPT_NODE,)

    generated = await compiled.ainvoke(
        Command(resume={"action": "approve", "selected_artifact_types": ["ppt"]}),
        config=config,
        context={"user_id": "1"},
    )
    assert generated["ppt_result"]["artifact_id"] == 101

    revised = await compiled.ainvoke(
        {
            "messages": [HumanMessage(content="Update the PPT")],
            "artifact_catalog": [{"id": 101, "type": "ppt", "title": "Slides"}],
        },
        config=config,
        context={"user_id": "1"},
    )
    assert revised["ppt_result"]["artifact_id"] == 102
    assert revised["revision_results"][0]["artifact_id"] == 102

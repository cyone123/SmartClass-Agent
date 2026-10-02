from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from app.core.conversation_orchestration import (
    ENTRY_ACTION_NAMES,
    INTAKE_ACTION_NAMES,
    START_TEACHING_DESIGN_TOOL,
    SUBMIT_METADATA_TOOL,
    ActionProtocolError,
    SubmitTeachingMetadataAction,
    build_bounded_intake_messages,
    close_teaching_task_update,
    is_explicit_intake_cancel,
    new_teaching_task_update,
    parse_action_message,
    safe_action_observation,
)


def _action_message(name: str, args: dict, *, content: str = "") -> AIMessage:
    return AIMessage(content=content, tool_calls=[{"name": name, "args": args, "id": "call-1"}])


def test_action_protocol_accepts_text_or_one_allowed_action() -> None:
    assert parse_action_message(AIMessage(content="你好"), allowed_names=ENTRY_ACTION_NAMES) is None
    parsed = parse_action_message(
        _action_message(START_TEACHING_DESIGN_TOOL, {"initial_request": " 设计函数课程 "}),
        allowed_names=ENTRY_ACTION_NAMES,
    )
    assert parsed is not None
    assert parsed.arguments.initial_request == "设计函数课程"


@pytest.mark.parametrize(
    "message",
    [
        AIMessage(content=""),
        _action_message("unknown", {}),
        _action_message(START_TEACHING_DESIGN_TOOL, {"initial_request": ""}),
        AIMessage(
            content="",
            tool_calls=[
                {"name": START_TEACHING_DESIGN_TOOL, "args": {"initial_request": "A"}, "id": "1"},
                {"name": START_TEACHING_DESIGN_TOOL, "args": {"initial_request": "B"}, "id": "2"},
            ],
        ),
    ],
)
def test_action_protocol_rejects_invalid_results(message: AIMessage) -> None:
    with pytest.raises(ActionProtocolError):
        parse_action_message(message, allowed_names=ENTRY_ACTION_NAMES)


def test_action_protocol_accepts_narration_before_action() -> None:
    action = parse_action_message(
        _action_message(START_TEACHING_DESIGN_TOOL, {"initial_request": "设计课程"}, content="我来处理"),
        allowed_names=ENTRY_ACTION_NAMES,
    )
    assert action.name == START_TEACHING_DESIGN_TOOL


def test_action_protocol_rejects_malformed_call_even_with_text() -> None:
    with pytest.raises(ActionProtocolError):
        parse_action_message(
            AIMessage(
                content="Let me help",
                invalid_tool_calls=[
                    {"name": START_TEACHING_DESIGN_TOOL, "args": "{", "id": "bad", "error": "invalid JSON"}
                ],
            ),
            allowed_names=ENTRY_ACTION_NAMES,
        )


def test_final_metadata_schema_enforces_required_fields_and_budgets() -> None:
    valid = SubmitTeachingMetadataAction(subject=" 数学 ", grade=" 初二 ", topic=" 二次函数 ")
    assert valid.subject == "数学"
    assert valid.core_points == []
    with pytest.raises(ValidationError):
        SubmitTeachingMetadataAction(subject="", grade="初二", topic="函数")
    with pytest.raises(ValidationError):
        SubmitTeachingMetadataAction(
            subject="数学",
            grade="初二",
            topic="函数",
            core_points=["1", "2", "3", "4", "5", "6"],
        )
    with pytest.raises(ActionProtocolError):
        parse_action_message(
            _action_message(SUBMIT_METADATA_TOOL, {"subject": "数学", "grade": "初二"}),
            allowed_names=INTAKE_ACTION_NAMES,
        )


def test_task_lifecycle_and_context_exclude_earlier_messages(monkeypatch) -> None:
    monkeypatch.setenv("TEACHING_INTAKE_CONTEXT_MAX_CHARS", "1000")
    monkeypatch.setenv("TEACHING_INTAKE_MAX_TURNS", "3")
    state = {
        "messages": [
            HumanMessage(content="旧任务：初一数学"),
            AIMessage(content="旧任务回答"),
            HumanMessage(content="请设计高中物理牛顿第一定律课程"),
        ]
    }
    update = new_teaching_task_update(state, "请设计高中物理牛顿第一定律课程")
    assert update["teaching_task_active"] is True
    assert update["teaching_metadata"] is None
    scoped = {
        **state,
        **update,
        "messages": [
            *state["messages"],
            AIMessage(content="课程时长是多少？"),
            HumanMessage(content="40分钟"),
        ],
    }
    context = build_bounded_intake_messages(scoped)
    combined = "\n".join(str(message.content) for message in context)
    assert "旧任务" not in combined
    assert "牛顿第一定律" in combined
    assert "40分钟" in combined
    assert close_teaching_task_update()["teaching_task_active"] is False


def test_new_task_boundary_keeps_attachment_summary_preceding_request() -> None:
    state = {
        "messages": [
            HumanMessage(content="old task"),
            SystemMessage(
                content="\u7528\u6237\u4e0a\u4f20\u7684\u9644\u4ef6\u5185\u5bb9\uff0c\u4f9b\u5f53\u524d\u8f6e\u5bf9\u8bdd\u53c2\u8003\uff1a\nsummary"
            ),
            HumanMessage(content="new task"),
        ]
    }
    update = new_teaching_task_update(state, "new task")
    assert update["teaching_task_start_message_index"] == 1
    context = build_bounded_intake_messages({**state, **update})
    assert any("summary" in str(message.content) for message in context)


def test_intake_context_includes_last_submission_for_correction() -> None:
    state = {
        "messages": [HumanMessage(content="设计函数课程"), HumanMessage(content="年级改成高二")],
        "teaching_task_start_message_index": 0,
        "teaching_task_initial_request": "设计函数课程",
        "last_submitted_teaching_metadata": {"subject": "数学", "grade": "高一", "topic": "函数"},
    }
    messages = build_bounded_intake_messages(state)
    assert isinstance(messages[0], SystemMessage)
    assert "高一" in str(messages[0].content)
    assert "年级改成高二" in str(messages[-1].content)


def test_intake_context_preserves_protocol_and_deduplicates_attachment_bodies() -> None:
    attachment = "\u7528\u6237\u4e0a\u4f20\u7684\u9644\u4ef6\u5185\u5bb9\uff0c\u4f9b\u5f53\u524d\u8f6e\u5bf9\u8bdd\u53c2\u8003\uff1a\nsummary"
    state = {
        "messages": [
            HumanMessage(content="Design a lesson"),
            SystemMessage(content=f"{attachment}\n\u9644\u4ef6\u5b58\u50a8\u8def\u5f84\uff1aone"),
            SystemMessage(content=f"{attachment}\n\u9644\u4ef6\u5b58\u50a8\u8def\u5f84\uff1atwo"),
            AIMessage(content="", tool_calls=[{"name": "internal", "args": {}, "id": "call-1"}]),
            ToolMessage(content="private result", tool_call_id="call-1"),
        ],
        "teaching_task_start_message_index": 0,
        "teaching_task_initial_request": "Design a lesson",
    }
    messages = build_bounded_intake_messages(state)
    combined = "\n".join(str(message.content) for message in messages)
    assert combined.count("summary") == 1
    assert "private result" in combined
    assert messages[-2].tool_calls[0]["id"] == messages[-1].tool_call_id


def test_intake_context_total_content_stays_within_configured_budget(monkeypatch) -> None:
    monkeypatch.setenv("TEACHING_INTAKE_CONTEXT_MAX_CHARS", "1000")
    state = {
        "messages": [
            HumanMessage(content="I" * 800),
            AIMessage(content="Q" * 800),
            HumanMessage(content="C" * 800),
        ],
        "teaching_task_start_message_index": 0,
        "teaching_task_initial_request": "I" * 800,
        "last_submitted_teaching_metadata": {
            "subject": "S" * 80,
            "grade": "G" * 80,
            "topic": "T" * 160,
        },
    }
    messages = build_bounded_intake_messages(state)
    assert sum(len(str(message.content)) for message in messages) <= 1000
    assert str(messages[0].content).startswith("Previously submitted metadata")
    assert "C" * 80 in str(messages[-1].content)


def test_cancel_detection_and_safe_observation_do_not_include_payloads() -> None:
    assert is_explicit_intake_cancel("\u53d6\u6d88\u672c\u6b21\u6559\u5b66\u8bbe\u8ba1")
    assert not is_explicit_intake_cancel("\u53d6\u6d88\u540e\u6539\u6210\u9ad8\u4e2d\u7269\u7406")
    fields = safe_action_observation(stage="teaching_intake", outcome="clarification")
    assert fields == {
        "stage": "teaching_intake",
        "outcome": "clarification",
        "fallback_used": False,
        "model_call_count": 1,
    }

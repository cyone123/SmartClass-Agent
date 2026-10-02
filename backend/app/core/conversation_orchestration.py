from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field, field_validator

from app.config import get_teaching_intake_context_max_chars, get_teaching_intake_max_turns
from app.core.model_access.messages import display_text, exchange_boundaries, recent_history

ArtifactTarget = Literal["ppt", "docx", "html-game"]
ATTACHMENT_SUMMARY_PREFIX = "\u7528\u6237\u4e0a\u4f20\u7684\u9644\u4ef6\u5185\u5bb9"

START_TEACHING_DESIGN_TOOL = "start_teaching_design"
REVISE_ARTIFACT_TOOL = "revise_artifact"
SUBMIT_METADATA_TOOL = "submit_metadata_for_review"
SEARCH_EXPERIENCE_TOOL = "search_experience_for_chat"
CANCEL_INTAKE_TOOL = "cancel_teaching_design"
RESTART_INTAKE_TOOL = "restart_teaching_design"

ENTRY_ACTION_NAMES = {
    START_TEACHING_DESIGN_TOOL,
    REVISE_ARTIFACT_TOOL,
    SEARCH_EXPERIENCE_TOOL,
}
INTAKE_ACTION_NAMES = {
    SUBMIT_METADATA_TOOL,
    CANCEL_INTAKE_TOOL,
    RESTART_INTAKE_TOOL,
}


class StartTeachingDesignAction(BaseModel):
    initial_request: str = Field(min_length=1, max_length=4000)

    @field_validator("initial_request")
    @classmethod
    def normalize_request(cls, value: str) -> str:
        return value.strip()


class ReviseArtifactAction(BaseModel):
    request: str = Field(min_length=1, max_length=4000)
    suggested_targets: list[ArtifactTarget] = Field(default_factory=list, max_length=3)

    @field_validator("request")
    @classmethod
    def normalize_request(cls, value: str) -> str:
        return value.strip()

    @field_validator("suggested_targets")
    @classmethod
    def deduplicate_targets(cls, value: list[ArtifactTarget]) -> list[ArtifactTarget]:
        return list(dict.fromkeys(value))


class SearchExperienceForChatAction(BaseModel):
    query: str = Field(min_length=1, max_length=1000)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return value.strip()


class SubmitTeachingMetadataAction(BaseModel):
    subject: str = Field(min_length=1, max_length=80)
    grade: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=160)
    course_duration: str | None = Field(default=None, max_length=80)
    core_points: list[str] = Field(default_factory=list, max_length=5)
    key_points: list[str] = Field(default_factory=list, max_length=5)
    difficult_points: list[str] = Field(default_factory=list, max_length=5)
    teaching_objectives: str | None = Field(default=None, max_length=500)

    @field_validator("subject", "grade", "topic")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("required metadata fields must not be blank")
        return normalized

    @field_validator("course_duration", "teaching_objectives")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("core_points", "key_points", "difficult_points")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if any(len(item) > 160 for item in normalized):
            raise ValueError("metadata list items must not exceed 160 characters")
        return normalized


class CancelTeachingDesignAction(BaseModel):
    response: str = Field(
        default="\u5df2\u53d6\u6d88\u672c\u6b21\u6559\u5b66\u8bbe\u8ba1\u9700\u6c42\u6536\u96c6\u3002",
        min_length=1,
        max_length=300,
    )

    @field_validator("response")
    @classmethod
    def normalize_response(cls, value: str) -> str:
        return value.strip()


class RestartTeachingDesignAction(BaseModel):
    initial_request: str = Field(min_length=1, max_length=4000)

    @field_validator("initial_request")
    @classmethod
    def normalize_request(cls, value: str) -> str:
        return value.strip()


ACTION_MODELS: dict[str, type[BaseModel]] = {
    START_TEACHING_DESIGN_TOOL: StartTeachingDesignAction,
    REVISE_ARTIFACT_TOOL: ReviseArtifactAction,
    SEARCH_EXPERIENCE_TOOL: SearchExperienceForChatAction,
    SUBMIT_METADATA_TOOL: SubmitTeachingMetadataAction,
    CANCEL_INTAKE_TOOL: CancelTeachingDesignAction,
    RESTART_INTAKE_TOOL: RestartTeachingDesignAction,
}

ACTION_DESCRIPTIONS = {
    START_TEACHING_DESIGN_TOOL: "Start teaching requirement collection for a new lesson-design request.",
    REVISE_ARTIFACT_TOOL: "Route a request to revise existing artifacts in the current thread.",
    SEARCH_EXPERIENCE_TOOL: "Search this user's reusable teaching Experience for an ordinary teaching discussion.",
    SUBMIT_METADATA_TOOL: "Submit complete canonical teaching metadata for user review.",
    CANCEL_INTAKE_TOOL: "Cancel the active teaching-intake workflow when the user explicitly asks to stop.",
    RESTART_INTAKE_TOOL: "Replace the active teaching task with a new explicit teaching-design request.",
}


def action_tool_schema(name: str) -> dict[str, Any]:
    model = ACTION_MODELS[name]
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": ACTION_DESCRIPTIONS[name],
            "parameters": model.model_json_schema(),
        },
    }


ENTRY_TOOL_SCHEMAS = [action_tool_schema(name) for name in sorted(ENTRY_ACTION_NAMES)]
INTAKE_TOOL_SCHEMAS = [action_tool_schema(name) for name in sorted(INTAKE_ACTION_NAMES)]


class ActionProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedAction:
    name: str
    arguments: BaseModel
    call_id: str


def parse_action_message(message: AIMessage, *, allowed_names: set[str]) -> ParsedAction | None:
    if message.invalid_tool_calls:
        raise ActionProtocolError("model returned malformed tool arguments")
    calls = list(message.tool_calls or [])
    text = message_text(message).strip()
    if not calls:
        if not text:
            raise ActionProtocolError("model returned neither visible text nor an action")
        return None
    if len(calls) != 1:
        raise ActionProtocolError("model must return exactly one action")
    call = calls[0]
    name = str(call.get("name") or "")
    if name not in allowed_names or name not in ACTION_MODELS:
        raise ActionProtocolError("model returned an unsupported action")
    arguments = call.get("args")
    if not isinstance(arguments, Mapping):
        raise ActionProtocolError("action arguments must be an object")
    try:
        validated = ACTION_MODELS[name].model_validate(dict(arguments))
    except Exception as exc:
        raise ActionProtocolError("action arguments failed validation") from exc
    return ParsedAction(name=name, arguments=validated, call_id=str(call.get("id") or "action"))


def message_text(message: BaseMessage) -> str:
    return display_text(message)


def new_teaching_task_update(state: Mapping[str, Any], initial_request: str) -> dict[str, Any]:
    messages = list(state.get("messages") or [])
    latest_human_index = next(
        (index for index in range(len(messages) - 1, -1, -1) if isinstance(messages[index], HumanMessage)),
        max(0, len(messages) - 1),
    )
    while latest_human_index > 0 and is_attachment_summary_message(messages[latest_human_index - 1]):
        latest_human_index -= 1
    return {
        "teaching_task_active": True,
        "teaching_task_scope_id": uuid.uuid4().hex,
        "teaching_task_start_message_index": latest_human_index,
        "teaching_task_initial_request": initial_request.strip(),
        "teaching_intake_turn_count": 0,
        "teaching_metadata": None,
        "last_submitted_teaching_metadata": None,
        "rag_context": "",
        "rag_results": [],
        "experience_memory_scope_key": "",
        "experience_memory_context": "",
        "experience_memory_selected_ids": [],
        "experience_memory_strategy": "none",
        "experience_memory_truncated": False,
        "experience_memory_degraded": False,
        "experience_memory_degradation_reason": "none",
    }


def close_teaching_task_update() -> dict[str, Any]:
    return {
        "teaching_task_active": False,
        "teaching_intake_turn_count": 0,
    }


def _copy_with_bounded_content(message: BaseMessage, content: str) -> BaseMessage:
    return message.model_copy(update={"content": content})


def is_attachment_summary_message(message: BaseMessage) -> bool:
    return isinstance(message, SystemMessage) and message_text(message).strip().startswith(ATTACHMENT_SUMMARY_PREFIX)


def build_bounded_intake_messages(state: Mapping[str, Any]) -> list[BaseMessage]:
    messages = list(state.get("messages") or [])
    start = int(state.get("teaching_task_start_message_index") or 0)
    start = min(max(start, 0), len(messages))
    task_messages = messages[start:]
    if any(
        isinstance(m, ToolMessage) or (isinstance(m, AIMessage) and (m.tool_calls or isinstance(m.content, list)))
        for m in task_messages
    ):
        # Native exchanges are atomic. Never truncate opaque blocks or separate results.
        unique = []
        seen = set()
        for message in task_messages:
            if is_attachment_summary_message(message):
                text = message_text(message).split("\n附件存储路径：", 1)[0]
                if text in seen:
                    continue
                seen.add(text)
            unique.append(message)
        bounded = recent_history(unique, get_teaching_intake_max_turns() * 2 + 2)
        boundaries = sorted(exchange_boundaries(bounded))
        budget = get_teaching_intake_context_max_chars()
        protected = []
        previous = state.get("last_submitted_teaching_metadata")
        if isinstance(previous, Mapping) and previous:
            content = (
                "Previously submitted metadata for correction; current explicit user corrections take precedence:\n"
                + json.dumps(dict(previous), ensure_ascii=False, sort_keys=True, default=str)
            )[: min(2000, max(80, budget // 4))]
            protected.append(SystemMessage(content=content))
            budget -= len(content)
        initial = str(state.get("teaching_task_initial_request") or "").strip()
        initial = initial[: min(4000, max(80, budget // 3))]
        if initial:
            protected.append(HumanMessage(content=initial))
            budget -= len(initial)
        selected = []
        for left, right in reversed(list(zip(boundaries, boundaries[1:]))):
            group = bounded[left:right]
            size = sum(len(json.dumps(m.model_dump(), ensure_ascii=False, default=str)) for m in group)
            if size > budget:
                break
            selected = group + selected
            budget -= size
        if boundaries[-1] != len(bounded):
            raise ActionProtocolError("unfinished action exchange in intake history")
        if initial and selected and isinstance(selected[0], HumanMessage) and message_text(selected[0]) == initial:
            selected = selected[1:]
        return [*protected, *selected]
    eligible: list[BaseMessage] = []
    seen_attachment_summaries: set[str] = set()
    for message in task_messages:
        content = message_text(message).strip()
        if (
            not isinstance(message, (HumanMessage, AIMessage, SystemMessage))
            or isinstance(message, ToolMessage)
            or not content
        ):
            continue
        if isinstance(message, AIMessage) and message.tool_calls:
            continue
        if is_attachment_summary_message(message):
            normalized_summary = content.split("\n\u9644\u4ef6\u5b58\u50a8\u8def\u5f84\uff1a", 1)[0]
            if normalized_summary in seen_attachment_summaries:
                continue
            seen_attachment_summaries.add(normalized_summary)
        eligible.append(message)
    maximum_turn_messages = get_teaching_intake_max_turns() * 2 + 2
    if len(eligible) > maximum_turn_messages:
        eligible = [eligible[0], *eligible[-(maximum_turn_messages - 1) :]]

    budget = get_teaching_intake_context_max_chars()
    protected: list[BaseMessage] = []
    remaining = budget
    previous = state.get("last_submitted_teaching_metadata")
    if isinstance(previous, Mapping) and previous:
        previous_content = (
            "Previously submitted metadata for correction; current explicit user corrections take precedence:\n"
            + json.dumps(dict(previous), ensure_ascii=False, sort_keys=True, default=str)
        )
        previous_content = previous_content[: min(2000, max(80, budget // 4))]
        protected.append(SystemMessage(content=previous_content))
        remaining -= len(previous_content)

    initial_request = str(state.get("teaching_task_initial_request") or "").strip()
    if initial_request:
        initial_content = initial_request[: min(4000, max(80, budget // 3), remaining)]
        if initial_content:
            protected.append(HumanMessage(content=initial_content))
            remaining -= len(initial_content)
        eligible = [message for message in eligible if message_text(message).strip() != initial_request]

    selected: list[BaseMessage] = []
    for message in reversed(eligible):
        content = message_text(message).strip()
        if not content:
            continue
        if len(content) > remaining:
            if remaining < 80:
                continue
            content = content[-remaining:]
        selected.append(_copy_with_bounded_content(message, content))
        remaining -= len(content)
        if remaining <= 0:
            break
    selected.reverse()
    return [*protected, *selected]


_EXPLICIT_CANCEL_PATTERN = re.compile(
    "^(?:\u53d6\u6d88|\u505c\u6b62|\u7b97\u4e86|\u4e0d\u505a\u4e86|\u9000\u51fa)"
    "(?:\u5427|\u4e86|\u8fd9\u4e2a|\u672c\u6b21|\u672c\u6b21\u6559\u5b66\u8bbe\u8ba1|"
    "\u6559\u5b66\u8bbe\u8ba1|\u5907\u8bfe)?"
    "[\u3002.!\uff01]?$",
    re.I,
)


def is_explicit_intake_cancel(message: str) -> bool:
    return bool(_EXPLICIT_CANCEL_PATTERN.fullmatch(message.strip()))


def safe_action_observation(
    *, stage: str, outcome: str, fallback_used: bool = False, model_call_count: int = 1
) -> dict[str, Any]:
    return {
        "stage": stage,
        "outcome": outcome,
        "fallback_used": fallback_used,
        "model_call_count": max(0, model_call_count),
    }

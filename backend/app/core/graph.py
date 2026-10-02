from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Literal, Mapping, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import Command, interrupt

from app.config import (
    get_profile_memory_context_max_chars,
    get_profile_memory_item_limit,
    get_teaching_intake_max_turns,
)
from app.core.conversation_orchestration import (
    CANCEL_INTAKE_TOOL,
    ENTRY_ACTION_NAMES,
    ENTRY_TOOL_SCHEMAS,
    INTAKE_ACTION_NAMES,
    INTAKE_TOOL_SCHEMAS,
    RESTART_INTAKE_TOOL,
    REVISE_ARTIFACT_TOOL,
    SEARCH_EXPERIENCE_TOOL,
    START_TEACHING_DESIGN_TOOL,
    SUBMIT_METADATA_TOOL,
    ActionProtocolError,
    CancelTeachingDesignAction,
    ParsedAction,
    RestartTeachingDesignAction,
    ReviseArtifactAction,
    SearchExperienceForChatAction,
    StartTeachingDesignAction,
    SubmitTeachingMetadataAction,
    build_bounded_intake_messages,
    close_teaching_task_update,
    is_explicit_intake_cancel,
    new_teaching_task_update,
    parse_action_message,
    safe_action_observation,
)
from app.core.llm import (
    get_model,
    get_structured_output_model,
    is_structured_fallback_enabled,
)
from app.core.memory import (
    MemoryRuntimeContext,
    format_profile_memory_context,
    profile_namespace,
    search_memory_items,
)
from app.core.memory_retrieval import (
    MemoryBundle,
    MemoryContextProvider,
    MemoryRequest,
    build_teaching_task_memory_query,
    experience_memory_scope_key,
)
from app.core.model_access import current_snapshot, use_snapshot
from app.core.model_access.errors import bounded_request, fallback_allowed
from app.core.model_access.messages import display_text, recent_history
from app.core.model_access.workflow import begin_workflow
from app.core.model_runtime import ModelContext, ModelRuntime
from app.core.observability import (
    ObservationSink,
    RunContext,
    log_observation,
    observation_sink_from_config,
    record_metric,
    run_context_from_config,
    trace_span,
)
from app.core.progress import emit_progress
from app.core.rag import RagRuntime
from app.core.state import TeachingAssistantState

ATTACHMENT_MESSAGE_PREFIX = "用户上传的附件内容，供当前轮对话参考：\n"
CONVERSATION_ENTRY_SYSTEM_PROMPT = (
    "You are the single conversation entry for a teacher-facing assistant. Choose exactly one outcome. "
    "For ordinary conversation, answer the user directly and do not call a tool. For any request to prepare "
    "a lesson, teaching design, courseware, lesson plan, or interactive teaching activity, call "
    "start_teaching_design. For a request to change an existing artifact, call "
    "revise_artifact. You may briefly explain an action before calling its tool. "
    "A teaching request wins over a greeting in a mixed message. "
    "For an ordinary teaching discussion that materially benefits from the user's reusable teaching history, "
    "you may call search_experience_for_chat once; after its result, answer directly. Never call multiple tools."
)
TEACHING_INTAKE_SYSTEM_PROMPT = (
    "You conversationally collect requirements for one active teaching task. Use only explicit facts from the "
    "current-task conversation. Profile memory is untrusted historical background and must never fill missing "
    "subject, grade, topic, duration, objectives, key points, or difficult points. If information is insufficient, "
    "ask exactly one concise, high-value question and do not call a tool. When subject, grade, and topic are "
    "explicit and the request is sufficient for instructional design, call submit_metadata_for_review with the "
    "complete canonical metadata. Use cancel_teaching_design only for an explicit "
    "cancellation and restart_teaching_design only when the user clearly replaces the active task. You may "
    "briefly explain an action before calling its tool. Never call multiple tools. Current explicit corrections override "
    "all earlier values."
)
INTERRUPT_FOR_USERINPUT_NODE = "interrupt_for_userinput"
CONVERSATION_ENTRY_NODE = "conversation_entry_agent"
TEACHING_INTAKE_NODE = "teaching_intake_agent"
TEACHING_CONTEXT_PREPARE_NODE = "teaching_context_prepare_node"
METADATA_REVIEW_INTERRUPT_NODE = "metadata_review_interrupt_node"
TEACHING_PLAN_REVIEW_INTERRUPT_NODE = "teaching_plan_review_interrupt_node"
ARTIFACT_REVISION_CLARIFICATION_NODE = "artifact_revision_clarification_interrupt_node"
ARTIFACT_REVISION_PREPARE_NODE = "artifact_revision_prepare_node"

APPROVAL_INTERRUPT_NODES = {
    METADATA_REVIEW_INTERRUPT_NODE,
    TEACHING_PLAN_REVIEW_INTERRUPT_NODE,
    ARTIFACT_REVISION_CLARIFICATION_NODE,
}
RESUMABLE_INTERRUPT_NODES = {
    INTERRUPT_FOR_USERINPUT_NODE,
    *APPROVAL_INTERRUPT_NODES,
}
APPROVAL_STAGE_BY_NODE = {
    METADATA_REVIEW_INTERRUPT_NODE: "metadata_review",
    TEACHING_PLAN_REVIEW_INTERRUPT_NODE: "teaching_plan_review",
}

ARTIFACT_TYPE_LABELS = {
    "ppt": "课件 PPT",
    "docx": "教案文档",
    "html-game": "互动内容",
}
GENERATABLE_ARTIFACT_TYPES: tuple[Literal["ppt", "docx", "html-game"], ...] = (
    "ppt",
    "docx",
    "html-game",
)
TEACHING_PLAN_ARTIFACT_OPTIONS: tuple[dict[str, Any], ...] = (
    {"type": "ppt", "label": "课件 PPT", "selected": True},
    {"type": "docx", "label": "DOCX 教案", "selected": True},
    {"type": "html-game", "label": "HTML 互动演示", "selected": True},
)
ARTIFACT_FEEDBACK_BY_TYPE = {
    "ppt": "modify_ppt",
    "docx": "modify_lesson_plan",
    "html-game": "modify_game",
}
ARTIFACT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ppt": ("ppt", "课件", "幻灯", "幻灯片", "slide", "slides", "powerpoint"),
    "docx": ("docx", "教案", "文档", "word", "lesson plan"),
    "html-game": ("html", "互动", "游戏", "小游戏", "活动页", "网页", "activity"),
}
REVISION_ALL_KEYWORDS = ("全部", "都", "所有", "一起", "all", "both", "三个")


memory_context_provider = MemoryContextProvider()
model_runtime = ModelRuntime(memory_provider=memory_context_provider)
# Optional injected runnables used by offline tests; production resolves per invocation.
conversation_entry_runnable = None
conversation_entry_fallback_runnable = None
teaching_intake_runnable = None
teaching_intake_fallback_runnable = None


def _action_model(override, *, intake=False, fallback=False):
    if override is not None:
        return override
    model = get_structured_output_model() if fallback else get_model(streaming=True)
    return model.bind_tools(INTAKE_TOOL_SCHEMAS if intake else ENTRY_TOOL_SCHEMAS, tool_choice="auto")


def build_input_messages(
    message: str,
    attachment_text: str | None = None,
    attachment_paths: list[str] | None = None,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    if attachment_text:
        messages.append(
            SystemMessage(content=(f"{ATTACHMENT_MESSAGE_PREFIX}{attachment_text}\n附件存储路径：{attachment_paths}"))
        )
    messages.append(HumanMessage(content=message))
    return messages


def _build_resume_message_update(user_input: Any) -> dict[str, list[BaseMessage]]:
    if isinstance(user_input, Mapping):
        return {
            "messages": build_input_messages(
                str(user_input.get("message", "") or ""),
                user_input.get("attachment_text"),
                user_input.get("attachment_paths"),
            )
        }
    return {"messages": build_input_messages(str(user_input))}


def _is_approve_action(user_input: Any) -> bool:
    return isinstance(user_input, Mapping) and user_input.get("action") == "approve"


def _build_approval_payload(
    stage: Literal["metadata_review", "teaching_plan_review", "artifact_revision_clarification"],
    *,
    metadata: Mapping[str, Any] | None = None,
    artifact_options: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if stage == "metadata_review":
        payload: dict[str, Any] = {
            "stage": stage,
            "title": "确认教学要素",
            "description": "已提取当前教学要素，请确认后继续生成教学设计方案。",
            "confirm_label": "确认并继续",
            "cancel_label": "取消并修改",
            "metadata": dict(metadata or {}),
        }
        return payload

    if stage == "teaching_plan_review":
        return {
            "stage": stage,
            "title": "确认教学设计方案",
            "description": "教学设计方案已生成，请确认是否继续生成课件、教案和互动内容。",
            "confirm_label": "确认并继续",
            "cancel_label": "取消并修改",
        }

    option_lines = []
    for artifact in artifact_options or ():
        artifact_type = str(artifact.get("type") or "")
        artifact_title = str(artifact.get("title") or ARTIFACT_TYPE_LABELS.get(artifact_type, artifact_type))
        option_lines.append(f"- {ARTIFACT_TYPE_LABELS.get(artifact_type, artifact_type)}：{artifact_title}")
    description = "你想修改哪个产物还不够明确。请直接输入更具体的修改要求，或者确认按当前会话里的全部产物一起修改。"
    if option_lines:
        description = f"{description}\n可选产物：\n" + "\n".join(option_lines)
    return {
        "stage": stage,
        "title": "确认修改目标",
        "description": description,
        "confirm_label": "默认修改全部",
        "cancel_label": "输入更具体要求",
    }


def get_pending_approval_payload(
    interrupts: Sequence[Any] | None,
    next_nodes: Sequence[str] | None,
) -> dict[str, Any] | None:
    pending_nodes = tuple(next_nodes or ())
    pending_interrupts = tuple(interrupts or ())
    for node_name in pending_nodes:
        if node_name not in APPROVAL_INTERRUPT_NODES:
            continue
        for pending_interrupt in pending_interrupts:
            payload = getattr(pending_interrupt, "value", None)
            if not isinstance(payload, Mapping):
                continue
            approval_payload = dict(payload)
            approval_payload["interrupt_id"] = getattr(pending_interrupt, "id", "")
            approval_payload.setdefault("stage", APPROVAL_STAGE_BY_NODE[node_name])
            return approval_payload
    return None


def _message_to_text(message) -> str:
    return display_text(message)


def _get_run_context(config: RunnableConfig | None, *, default_run_id: str = "graph") -> RunContext:
    configurable = config.get("configurable") if isinstance(config, dict) else None
    if isinstance(configurable, dict) and isinstance(configurable.get("run_context"), RunContext):
        return configurable["run_context"]
    return run_context_from_config(config, default_run_id=default_run_id).with_agent("main_graph")


def _get_observation_sink(config: RunnableConfig | None) -> ObservationSink:
    return observation_sink_from_config(config)


def _emit_committed_text(config: RunnableConfig | None, value: str) -> None:
    configurable = config.get("configurable") if isinstance(config, dict) else None
    emitter = configurable.get("root_text_event_emitter") if isinstance(configurable, dict) else None
    if callable(emitter) and value:
        emitter(value)


def _visible_action_messages(response: AIMessage) -> list[BaseMessage]:
    """Persist full protocol history; public exits independently extract text."""
    return [
        response,
        *[
            ToolMessage(content="Action accepted by SmartClass.", tool_call_id=call["id"], name=call["name"])
            for call in response.tool_calls
        ],
    ]


def _safe_json_size(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return len(str(value))


def _graph_node_summary(
    node_name: str,
    state: TeachingAssistantState,
    result: Any | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "node_name": node_name,
        "input_size": _safe_json_size(
            {
                "keys": sorted(state.keys()),
                "message_count": len(state.get("messages", []) or []),
                "plan_id": state.get("plan_id"),
            }
        ),
    }
    if result is not None:
        fields["output_size"] = _safe_json_size(result)
    if node_name == "rag_retrieval_node":
        rag_results = result.get("rag_results") if isinstance(result, Mapping) else state.get("rag_results")
        fields["rag_result_count"] = len(rag_results or [])
    elif node_name == "artifact_revision_router_node":
        update = getattr(result, "update", None)
        target_source = update if isinstance(update, Mapping) else result if isinstance(result, Mapping) else state
        targets = target_source.get("revision_targets") if isinstance(target_source, Mapping) else None
        fields["selected_artifact_types"] = [
            str(item.get("type") or "") for item in (targets or []) if isinstance(item, Mapping)
        ]
    elif node_name == "artifact_fan_in_node":
        results = result.get("revision_results") if isinstance(result, Mapping) else state.get("revision_results")
        fields["artifact_result_count"] = len(results or [])
    return fields


def _observed_graph_node(node_name: str, func: Callable[..., Any]) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(func):

        async def async_wrapper(
            state: TeachingAssistantState,
            config: Optional[RunnableConfig] = None,
            runtime: Runtime[MemoryRuntimeContext] | None = None,
        ):
            context = _get_run_context(config).with_model_config(
                (state.get("model_config_snapshot") or {}).get("fingerprint"), state.get("model_workflow_id")
            )
            config = {
                **(config or {}),
                "configurable": {**((config or {}).get("configurable") or {}), "run_context": context},
            }
            sink = _get_observation_sink(config)
            with (
                use_snapshot(state.get("model_config_snapshot") or current_snapshot()),
                trace_span(
                    f"graph.node.{node_name}",
                    context=context,
                    sink=sink,
                    fields=_graph_node_summary(node_name, state),
                ) as span_fields,
            ):
                if "runtime" in inspect.signature(func).parameters:
                    result = await func(state, config=config, runtime=runtime)
                else:
                    result = await func(state, config)
                span_fields.update(_graph_node_summary(node_name, state, result))
                return result

        return async_wrapper

    def sync_wrapper(
        state: TeachingAssistantState,
        config: Optional[RunnableConfig] = None,
    ):
        context = _get_run_context(config).with_model_config(
            (state.get("model_config_snapshot") or {}).get("fingerprint"), state.get("model_workflow_id")
        )
        config = {
            **(config or {}),
            "configurable": {**((config or {}).get("configurable") or {}), "run_context": context},
        }
        sink = _get_observation_sink(config)
        with (
            use_snapshot(state.get("model_config_snapshot") or current_snapshot()),
            trace_span(
                f"graph.node.{node_name}",
                context=context,
                sink=sink,
                fields=_graph_node_summary(node_name, state),
            ) as span_fields,
        ):
            result = func(state, config)
            span_fields.update(_graph_node_summary(node_name, state, result))
            return result

    return sync_wrapper


def _latest_user_message_text(state: TeachingAssistantState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return _message_to_text(message).strip()
    return ""


def _artifact_catalog_summary(state: TeachingAssistantState) -> str:
    artifacts = state.get("artifact_catalog") or []
    if not artifacts:
        return "No ready artifacts exist in the current thread."
    lines = []
    for artifact in artifacts:
        artifact_type = str(artifact.get("type") or "")
        label = ARTIFACT_TYPE_LABELS.get(artifact_type, artifact_type)
        title = str(artifact.get("title") or label)
        revision_number = artifact.get("revision_number")
        revision_text = f" v{revision_number}" if revision_number else ""
        lines.append(f"- {label}{revision_text}: {title}")
    return "\n".join(lines)


def _feedback_type_for_targets(target_types: Sequence[str]) -> str | None:
    unique_targets = list(dict.fromkeys(target_types))
    if len(unique_targets) > 1:
        return "modify_all"
    if len(unique_targets) == 1:
        return ARTIFACT_FEEDBACK_BY_TYPE.get(unique_targets[0])
    return None


def _infer_revision_targets_from_text(
    message: str,
    artifact_catalog: Sequence[Mapping[str, Any]],
) -> tuple[str | None, list[str], bool]:
    available_types = [
        artifact_type
        for artifact_type in (str(item.get("type") or "") for item in artifact_catalog)
        if artifact_type in ARTIFACT_TYPE_LABELS
    ]
    unique_available_types = list(dict.fromkeys(available_types))
    lowered = message.casefold()

    if any(keyword in lowered for keyword in REVISION_ALL_KEYWORDS):
        return "modify_all", unique_available_types, False

    explicit_targets = [
        artifact_type
        for artifact_type, keywords in ARTIFACT_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords) and artifact_type in unique_available_types
    ]

    if explicit_targets:
        explicit_targets = list(dict.fromkeys(explicit_targets))
        if len(explicit_targets) > 1:
            return "modify_all", explicit_targets, False
        target_type = explicit_targets[0]
        return ARTIFACT_FEEDBACK_BY_TYPE[target_type], [target_type], False

    if len(unique_available_types) == 1:
        target_type = unique_available_types[0]
        return ARTIFACT_FEEDBACK_BY_TYPE[target_type], [target_type], False

    if unique_available_types:
        return None, [], True

    return None, [], False


def _pending_result_for_artifact_type(
    artifact_type: Literal["ppt", "docx", "html-game"],
) -> dict[str, Any]:
    return {
        "status": "pending",
        "artifact_id": None,
        "artifact_type": artifact_type,
        "title": None,
        "error": None,
    }


def _normalize_generation_targets(
    selected_types: Sequence[str] | None,
) -> list[Literal["ppt", "docx", "html-game"]]:
    if selected_types is None:
        return list(GENERATABLE_ARTIFACT_TYPES)
    return [
        artifact_type
        for artifact_type in dict.fromkeys(str(item) for item in selected_types)
        if artifact_type in GENERATABLE_ARTIFACT_TYPES
    ]


def _generation_result_reset_update(
    selected_types: Sequence[str] | None = None,
) -> dict[str, Any]:
    normalized_targets = _normalize_generation_targets(selected_types)
    update: dict[str, Any] = {
        "generation_targets": normalized_targets,
        "revision_targets": [],
        "revision_source_artifacts": [],
        "revision_results": [],
        "user_feedback": None,
        "feedback_type": None,
    }
    if "ppt" in normalized_targets:
        update["ppt_result"] = _pending_result_for_artifact_type("ppt")
    if "docx" in normalized_targets:
        update["lesson_plan_result"] = _pending_result_for_artifact_type("docx")
    if "html-game" in normalized_targets:
        update["game_result"] = _pending_result_for_artifact_type("html-game")
    return update


def _revision_result_reset_update(
    selected_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    update: dict[str, Any] = {
        "revision_results": [],
    }
    target_types = {str(artifact.get("type") or "") for artifact in selected_artifacts}
    if "ppt" in target_types:
        update["ppt_result"] = _pending_result_for_artifact_type("ppt")
    if "docx" in target_types:
        update["lesson_plan_result"] = _pending_result_for_artifact_type("docx")
    if "html-game" in target_types:
        update["game_result"] = _pending_result_for_artifact_type("html-game")
    return update


def _result_key_for_artifact_type(artifact_type: str) -> str | None:
    return {
        "ppt": "ppt_result",
        "docx": "lesson_plan_result",
        "html-game": "game_result",
    }.get(artifact_type)


def _build_conversation_entry_messages(state: TeachingAssistantState) -> list[BaseMessage]:
    recent_messages = [message for message in state.get("messages", []) if isinstance(message, BaseMessage)]
    return [
        SystemMessage(content=CONVERSATION_ENTRY_SYSTEM_PROMPT),
        SystemMessage(content=f"Trusted current-thread artifact catalog:\n{_artifact_catalog_summary(state)}"),
        *recent_history(recent_messages, 8),
    ]


@bounded_request
async def _invoke_action_protocol(
    *,
    messages: Sequence[BaseMessage],
    context: ModelContext,
    primary_runnable: Any,
    fallback_runnable: Any,
    allowed_names: set[str],
    stage: str,
    config: RunnableConfig | None,
    memory_bundle: MemoryBundle | None = None,
) -> tuple[AIMessage, ParsedAction | None, bool]:
    failures: list[Exception] = []
    attempts = [(primary_runnable, False)]
    if is_structured_fallback_enabled():
        attempts.append((fallback_runnable, True))
    for runnable, fallback_used in attempts:
        emitted_text = False

        def emit_chunk(chunk: BaseMessage) -> None:
            nonlocal emitted_text
            text = _message_to_text(chunk)
            if text:
                emitted_text = True
                _emit_committed_text(config, text)

        try:
            response = await model_runtime.invoke(
                runnable,
                messages,
                context,
                memory_bundle=memory_bundle,
                fields={"stage": stage, "fallback_used": fallback_used},
                config=config,
                on_chunk=emit_chunk,
            )
            if not isinstance(response, AIMessage):
                raise ActionProtocolError("action model did not return an AI message")
            action = parse_action_message(response, allowed_names=allowed_names)
            log_observation(
                "graph.action_protocol",
                context=_get_run_context(config),
                sink=_get_observation_sink(config),
                status="success",
                fields=safe_action_observation(
                    stage=stage,
                    outcome=action.name if action is not None else "text",
                    fallback_used=fallback_used,
                    model_call_count=len(failures) + 1,
                ),
            )
            return response, action, fallback_used
        except Exception as exc:
            if not fallback_allowed(exc):
                raise
            failures.append(exc)
            log_observation(
                "graph.action_protocol",
                context=_get_run_context(config),
                sink=_get_observation_sink(config),
                status="failed",
                fields={
                    **safe_action_observation(
                        stage=stage,
                        outcome="invalid",
                        fallback_used=fallback_used,
                        model_call_count=len(failures),
                    ),
                    "error_category": "model_error" if not isinstance(exc, ActionProtocolError) else "validation_error",
                    "error_type": exc.__class__.__name__,
                },
            )
            # Once text is visible, retrying would concatenate two different answers.
            # Valid text + action responses pass validation above and never take this path.
            if emitted_text:
                raise RuntimeError("The response was interrupted after streaming began") from exc
    raise ActionProtocolError("all bounded action-protocol attempts failed") from failures[-1]


def _observe_teaching_scope_transition(config: RunnableConfig | None, transition: str) -> None:
    log_observation(
        "graph.teaching_scope_transition",
        context=_get_run_context(config),
        sink=_get_observation_sink(config),
        status="success",
        fields={"stage": "teaching_intake", "transition": transition},
    )


async def conversation_entry_agent(
    state: TeachingAssistantState,
    config: Optional[RunnableConfig] = None,
    runtime: Runtime[MemoryRuntimeContext] | None = None,
):
    reporter = emit_progress(config, "intent_recognition", "running")
    messages = _build_conversation_entry_messages(state)
    context = _model_context(state, config, runtime)
    try:
        response, action, fallback_used = await _invoke_action_protocol(
            messages=messages,
            context=context,
            primary_runnable=_action_model(conversation_entry_runnable, intake=False, fallback=False),
            fallback_runnable=_action_model(conversation_entry_fallback_runnable, intake=False, fallback=True),
            allowed_names=ENTRY_ACTION_NAMES,
            stage="conversation_entry",
            config=config,
        )
        if action is None:
            if reporter:
                reporter.emit("intent_recognition", "success", detail="识别为普通对话")
            return Command(
                update={"messages": [response], "teaching_task_active": False},
                goto=END,
            )

        if action.name == START_TEACHING_DESIGN_TOOL:
            arguments = action.arguments
            if not isinstance(arguments, StartTeachingDesignAction):
                raise ActionProtocolError("invalid teaching action")
            update = {**new_teaching_task_update(state, arguments.initial_request), **begin_workflow(state)}
            update["messages"] = _visible_action_messages(response)
            _observe_teaching_scope_transition(config, "started")
            if reporter:
                reporter.emit("intent_recognition", "success", detail="识别为教学设计请求")
            return Command(update=update, goto=TEACHING_INTAKE_NODE)

        if action.name == REVISE_ARTIFACT_TOOL:
            arguments = action.arguments
            if not isinstance(arguments, ReviseArtifactAction):
                raise ActionProtocolError("invalid revision action")
            if reporter:
                reporter.emit("intent_recognition", "success", detail="识别为产物修改请求")
            _observe_teaching_scope_transition(config, "closed_for_revision")
            return Command(
                update={
                    **begin_workflow(state),
                    "user_feedback": arguments.request,
                    "revision_target_hints": arguments.suggested_targets,
                    "teaching_task_active": False,
                    "messages": _visible_action_messages(response),
                },
                goto="artifact_revision_router_node",
            )

        if action.name == SEARCH_EXPERIENCE_TOOL:
            arguments = action.arguments
            if not isinstance(arguments, SearchExperienceForChatAction):
                raise ActionProtocolError("invalid memory-search action")
            memory_request = MemoryRequest(
                purpose="normal_chat",
                query=build_teaching_task_memory_query(
                    messages=[HumanMessage(content=arguments.query)],
                    initial_request=arguments.query,
                    task_kind="normal_chat",
                ),
            )
            bundle = await model_runtime.resolve_memory(context, memory_request)
            follow_up_messages = [
                *messages,
                response,
                ToolMessage(
                    content="Bounded reusable teaching Experience is now available as historical background.",
                    tool_call_id=action.call_id,
                    name=SEARCH_EXPERIENCE_TOOL,
                ),
            ]
            final_response, final_action, second_fallback = await _invoke_action_protocol(
                messages=follow_up_messages,
                context=context,
                primary_runnable=_action_model(conversation_entry_runnable, intake=False, fallback=False),
                fallback_runnable=_action_model(conversation_entry_fallback_runnable, intake=False, fallback=True),
                allowed_names={START_TEACHING_DESIGN_TOOL, REVISE_ARTIFACT_TOOL},
                stage="conversation_entry_memory_answer",
                config=config,
                memory_bundle=bundle,
            )
            if final_action is not None:
                raise ActionProtocolError("memory-assisted ordinary chat must finish with visible text")
            if reporter:
                reporter.emit("intent_recognition", "success", detail="识别为普通教学对话并已结合历史经验回答")
            log_observation(
                "graph.entry.completed",
                context=_get_run_context(config),
                sink=_get_observation_sink(config),
                status="success",
                fields=safe_action_observation(
                    stage="conversation_entry",
                    outcome="memory_assisted_text",
                    fallback_used=fallback_used or second_fallback,
                    model_call_count=(2 if fallback_used else 1) + (2 if second_fallback else 1),
                ),
            )
            return Command(
                update={
                    "messages": [*_visible_action_messages(response), final_response],
                    "teaching_task_active": False,
                },
                goto=END,
            )
        raise ActionProtocolError("unsupported entry action")
    except ActionProtocolError:
        if reporter:
            reporter.emit("intent_recognition", "failed", detail="未能可靠理解当前请求")
        safe_response = AIMessage(content="我暂时没能可靠理解这个请求。请换一种更明确的说法，我会继续帮你。")
        _emit_committed_text(config, _message_to_text(safe_response))
        return Command(
            update={"messages": [safe_response]},
            goto=END,
        )


async def teaching_intake_agent(
    state: TeachingAssistantState,
    config: Optional[RunnableConfig] = None,
    runtime: Runtime[MemoryRuntimeContext] | None = None,
):
    reporter = emit_progress(config, "metadata_structuring", "running")
    latest_message = _latest_user_message_text(state)
    if is_explicit_intake_cancel(latest_message):
        if reporter:
            reporter.emit("metadata_structuring", "success", detail="已取消教学需求收集")
        cancel_response = AIMessage(content="已取消本次教学设计需求收集。")
        _observe_teaching_scope_transition(config, "cancelled")
        _emit_committed_text(config, _message_to_text(cancel_response))
        return Command(
            update={
                **close_teaching_task_update(),
                "model_workflow_active": False,
                "messages": [cancel_response],
            },
            goto=END,
        )

    messages = [SystemMessage(content=TEACHING_INTAKE_SYSTEM_PROMPT), *build_bounded_intake_messages(state)]
    if int(state.get("teaching_intake_turn_count") or 0) >= get_teaching_intake_max_turns():
        messages.append(
            SystemMessage(
                content="If clarification is still necessary, ask for all remaining required facts in one concise question."
            )
        )
    try:
        response, action, _ = await _invoke_action_protocol(
            messages=messages,
            context=_model_context(state, config, runtime),
            primary_runnable=_action_model(teaching_intake_runnable, intake=True, fallback=False),
            fallback_runnable=_action_model(teaching_intake_fallback_runnable, intake=True, fallback=True),
            allowed_names=INTAKE_ACTION_NAMES,
            stage="teaching_intake",
            config=config,
        )
    except ActionProtocolError:
        response = AIMessage(content="为了继续设计，请补充本节课的学科、年级和具体课题。")
        _emit_committed_text(config, _message_to_text(response))
        action = None

    if action is None:
        turn_count = int(state.get("teaching_intake_turn_count") or 0) + 1
        if reporter:
            reporter.emit("metadata_structuring", "success", detail="已识别缺失信息并发起追问")
        return Command(
            update={"messages": [response], "teaching_intake_turn_count": turn_count},
            goto=INTERRUPT_FOR_USERINPUT_NODE,
        )

    if action.name == SUBMIT_METADATA_TOOL:
        arguments = action.arguments
        if not isinstance(arguments, SubmitTeachingMetadataAction):
            raise ActionProtocolError("invalid final metadata action")
        metadata = {**arguments.model_dump(), "is_complete": True}
        if reporter:
            reporter.emit("metadata_structuring", "success", detail="已形成完整教学要素，等待确认")
        _observe_teaching_scope_transition(config, "submitted")
        return Command(
            update={
                "teaching_metadata": metadata,
                "last_submitted_teaching_metadata": metadata,
                "teaching_task_active": False,
                "messages": _visible_action_messages(response),
            },
            goto=METADATA_REVIEW_INTERRUPT_NODE,
        )

    if action.name == CANCEL_INTAKE_TOOL:
        arguments = action.arguments
        if not isinstance(arguments, CancelTeachingDesignAction):
            raise ActionProtocolError("invalid cancel action")
        if reporter:
            reporter.emit("metadata_structuring", "success", detail="已取消教学需求收集")
        cancel_response = AIMessage(content=arguments.response)
        _observe_teaching_scope_transition(config, "cancelled")
        _emit_committed_text(config, _message_to_text(cancel_response))
        return Command(
            update={
                **close_teaching_task_update(),
                "model_workflow_active": False,
                "messages": [*_visible_action_messages(response), cancel_response],
            },
            goto=END,
        )

    if action.name == RESTART_INTAKE_TOOL:
        arguments = action.arguments
        if not isinstance(arguments, RestartTeachingDesignAction):
            raise ActionProtocolError("invalid restart action")
        if reporter:
            reporter.emit("metadata_structuring", "success", detail="已切换到新的教学任务")
        _observe_teaching_scope_transition(config, "restarted")
        return Command(
            update={
                **new_teaching_task_update(state, arguments.initial_request),
                **begin_workflow(state),
                "messages": _visible_action_messages(response),
            },
            goto=TEACHING_INTAKE_NODE,
        )

    raise ActionProtocolError("unsupported intake action")


def metadata_review_interrupt_node(
    state: TeachingAssistantState,
    config: Optional[RunnableConfig] = None,
):
    reporter = emit_progress(config, "metadata_review", "running")
    _ = config
    user_input = interrupt(
        _build_approval_payload(
            "metadata_review",
            metadata=state.get("teaching_metadata") or {},
        )
    )
    if _is_approve_action(user_input):
        if reporter:
            reporter.emit("metadata_review", "success", detail="已确认教学要素")
        return Command(goto=TEACHING_CONTEXT_PREPARE_NODE)
    # if reporter:
    #             reporter.emit("metadata_review", "success", detail="已修改教学要素")
    return Command(
        update={
            **_build_resume_message_update(user_input),
            "teaching_task_active": True,
        },
        goto=TEACHING_INTAKE_NODE,
    )


def _runtime_user_id(runtime: Runtime[MemoryRuntimeContext] | None) -> str | None:
    if runtime is None or not isinstance(runtime.context, dict):
        return None
    return runtime.context.get("user_id")


def _runtime_store(runtime: Runtime[MemoryRuntimeContext] | None) -> BaseStore | None:
    if runtime is None:
        return None
    return runtime.store


async def profile_memory_load_node(
    state: TeachingAssistantState,
    runtime: Runtime[MemoryRuntimeContext],
    config: Optional[RunnableConfig] = None,
):
    if state.get("profile_memory_loaded"):
        return {}
    started = time.perf_counter()
    store = _runtime_store(runtime)
    user_id = _runtime_user_id(runtime)
    memories: list[dict[str, Any]] = []
    outcome = "empty"
    try:
        if store is None:
            raise RuntimeError("memory Store is unavailable")
        memories = await search_memory_items(
            store,
            profile_namespace(user_id),
            limit=get_profile_memory_item_limit(),
        )
        outcome = "success" if memories else "empty"
    except Exception:
        outcome = "degraded"
    maximum = get_profile_memory_context_max_chars()
    unbounded = format_profile_memory_context(memories, max_chars=None)
    profile_context = unbounded[:maximum]
    truncated = len(unbounded) > maximum
    log_observation(
        "memory.profile_initialization",
        context=run_context_from_config(config, default_run_id="memory").with_agent("memory"),
        sink=observation_sink_from_config(config),
        status="failed" if outcome == "degraded" else "success",
        fields={
            "outcome": outcome,
            "item_count": len(memories),
            "truncated": truncated,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return {
        "profile_memory_loaded": True,
        "profile_memory_context": profile_context,
        "profile_memory_item_count": len(memories),
        "profile_memory_truncated": truncated,
    }


def _model_context(
    state: TeachingAssistantState,
    config: RunnableConfig | None,
    runtime: Runtime[MemoryRuntimeContext] | None = None,
) -> ModelContext:
    return ModelContext(
        user_id=_runtime_user_id(runtime) or str(run_context_from_config(config).user_id or ""),
        store=_runtime_store(runtime),
        profile_memory_context=str(state.get("profile_memory_context") or ""),
        model_workflow_id=state.get("model_workflow_id"),
        model_config_fingerprint=(state.get("model_config_snapshot") or {}).get("fingerprint"),
        run_context=run_context_from_config(config)
        .with_agent("main_graph")
        .with_model_config(
            (state.get("model_config_snapshot") or {}).get("fingerprint"), state.get("model_workflow_id")
        ),
        observation_sink=observation_sink_from_config(config),
    )


def _teaching_design_memory_request(state: TeachingAssistantState) -> MemoryRequest:
    return MemoryRequest(
        purpose="teaching_design",
        query=build_teaching_task_memory_query(
            messages=list(state.get("messages", []) or []),
            teaching_metadata=state.get("teaching_metadata") or {},
            initial_request=str(state.get("teaching_task_initial_request") or ""),
            task_kind="teaching_design",
        ),
    )


def _artifact_revision_memory_request(state: TeachingAssistantState, *, include_revision: bool) -> MemoryRequest:
    return MemoryRequest(
        purpose="artifact_revision",
        query=build_teaching_task_memory_query(
            messages=list(state.get("messages", []) or []),
            teaching_metadata=state.get("teaching_metadata") or {},
            initial_request=str(state.get("teaching_task_initial_request") or ""),
            task_kind="artifact_revision",
            revision_request=str(state.get("user_feedback") or "") if include_revision else "",
        ),
    )


def _experience_bundle_from_state(state: TeachingAssistantState) -> MemoryBundle:
    return MemoryBundle(
        context=str(state.get("experience_memory_context") or ""),
        selected_ids=tuple(str(value) for value in state.get("experience_memory_selected_ids") or []),
        strategy=str(state.get("experience_memory_strategy") or "none"),
        selected_count=len(state.get("experience_memory_selected_ids") or []),
        truncated=bool(state.get("experience_memory_truncated")),
        degraded=bool(state.get("experience_memory_degraded")),
        degradation_reason=str(state.get("experience_memory_degradation_reason") or "none"),
        reused=True,
    )


async def _ensure_experience_snapshot(
    state: TeachingAssistantState,
    *,
    request: MemoryRequest,
    config: RunnableConfig | None,
    runtime: Runtime[MemoryRuntimeContext] | None,
) -> tuple[MemoryBundle, dict[str, Any]]:
    scope_key = experience_memory_scope_key(request)
    reused = state.get("experience_memory_scope_key") == scope_key
    if reused:
        bundle = _experience_bundle_from_state(state)
        update: dict[str, Any] = {}
    else:
        model_context = _model_context(state, config, runtime)
        bundle = await memory_context_provider.resolve(
            store=model_context.store,
            user_id=model_context.user_id,
            request=request,
            run_context=model_context.run_context,
            observation_sink=model_context.observation_sink,
        )
        update = {
            "experience_memory_scope_key": scope_key,
            "experience_memory_context": bundle.context,
            "experience_memory_selected_ids": list(bundle.selected_ids),
            "experience_memory_strategy": bundle.strategy,
            "experience_memory_truncated": bundle.truncated,
            "experience_memory_degraded": bundle.degraded,
            "experience_memory_degradation_reason": bundle.degradation_reason,
        }
    log_observation(
        "memory.experience_snapshot",
        context=run_context_from_config(config, default_run_id="memory").with_agent("memory"),
        sink=observation_sink_from_config(config),
        status="success" if not bundle.degraded else "failed",
        fields={
            "purpose": request.purpose,
            "strategy": bundle.strategy,
            "selected_count": bundle.selected_count,
            "truncated": bundle.truncated,
            "reused": reused,
            "refreshed": not reused,
            "degraded": bundle.degraded,
            "degradation_reason": bundle.degradation_reason,
            "duration_ms": bundle.duration_ms,
        },
    )
    return bundle, update


def interrupt_for_userinput(state: TeachingAssistantState):
    user_input = interrupt({"question": state["messages"][-1].content})
    if isinstance(user_input, dict):
        return {
            "messages": build_input_messages(
                str(user_input.get("message", "") or ""),
                user_input.get("attachment_text"),
                user_input.get("attachment_paths"),
            )
        }
    return {"messages": build_input_messages(str(user_input))}


def _build_rag_query(state: TeachingAssistantState) -> str:
    metadata = state.get("teaching_metadata") or {}
    human_messages = [
        _message_to_text(msg).strip() for msg in state.get("messages", []) if isinstance(msg, HumanMessage)
    ]
    query_parts = [
        f"教学元数据: {json.dumps(metadata, ensure_ascii=False)}",
        f"用户问题: {' '.join(message for message in human_messages if message)}",
    ]
    return "\n".join(part for part in query_parts if part.strip())


async def teaching_design_planner(
    state: TeachingAssistantState,
    config: Optional[RunnableConfig] = None,
    runtime: Runtime[MemoryRuntimeContext] | None = None,
):
    reporter = emit_progress(config, "teaching_design", "running")
    system_prompt = (
        "你是教师助手中的教学设计规划节点。"
        "请根据用户需求、结构化教学要素和检索上下文，输出一份完整、可执行的教学设计方案。"
        "这份结果会直接用于后续课件、教案和互动内容生成。\n"
        f"教学元数据：{state.get('teaching_metadata')}\n"
        f"RAG 上下文：{state.get('rag_context', '')}"
    )
    try:
        if state.get("experience_memory_scope_key"):
            bundle = _experience_bundle_from_state(state)
            snapshot_update: dict[str, Any] = {}
        else:
            bundle, snapshot_update = await _ensure_experience_snapshot(
                state,
                request=_teaching_design_memory_request(state),
                config=config,
                runtime=runtime,
            )
        messages = [SystemMessage(content=system_prompt), *list(state.get("messages", []) or [])]
        response = await model_runtime.invoke(
            "main",
            messages,
            _model_context(state, config, runtime),
            memory_bundle=bundle,
            fields={"node": "teaching_design_planner"},
        )
        if reporter:
            reporter.emit("teaching_design", "success", detail="已生成教学设计方案")
        return {
            **snapshot_update,
            "teaching_design_plan": _message_to_text(response).strip(),
            "messages": [response],
        }
    except Exception as exc:
        if reporter:
            reporter.emit("teaching_design", "failed", detail=str(exc))
        raise


def teaching_plan_review_interrupt_node(
    state: TeachingAssistantState,
    config: Optional[RunnableConfig] = None,
):
    reporter = emit_progress(config, "teaching_plan_review", "running", detail="等待教师确认教学设计")
    user_input = interrupt(_build_approval_payload("teaching_plan_review"))
    if _is_approve_action(user_input):
        selected_types = _normalize_generation_targets(
            user_input.get("selected_artifact_types") if isinstance(user_input, Mapping) else None
        )
        if not selected_types:
            error_message = "请至少选择一个要生成的产物。"
            if reporter:
                reporter.emit("teaching_plan_review", "failed", detail=error_message)
            return Command(
                update={"messages": [AIMessage(content=error_message)]},
                goto=END,
            )
        if reporter:
            reporter.emit("teaching_plan_review", "success", detail="已确认教学设计")
        return Command(
            update=_generation_result_reset_update(selected_types),
            goto=_clean_goto_nodes(
                [
                    "ppt_generate_node" if "ppt" in selected_types else None,
                    "docx_generate_node" if "docx" in selected_types else None,
                    "html_game_generate_node" if "html-game" in selected_types else None,
                ]
            ),
        )
    return Command(
        update=_build_resume_message_update(user_input),
        goto=TEACHING_CONTEXT_PREPARE_NODE,
    )


def artifact_revision_router_node(
    state: TeachingAssistantState,
    config: Optional[RunnableConfig] = None,
):
    reporter = emit_progress(config, "artifact_revision_routing", "running")
    artifact_catalog = state.get("artifact_catalog") or []
    if not artifact_catalog:
        if reporter:
            reporter.emit("artifact_revision_routing", "failed", detail="当前会话没有可修改的产物")
        return Command(
            update={
                "messages": [
                    AIMessage(content="当前会话还没有可修改的产物。请先生成课件、教案或互动内容，再提出修改要求。")
                ]
            },
            goto=END,
        )

    latest_message = _latest_user_message_text(state)
    target_hints = [target for target in state.get("revision_target_hints", []) if target in GENERATABLE_ARTIFACT_TYPES]
    if target_hints:
        target_types = target_hints
        feedback_type = _feedback_type_for_targets(target_types)
        needs_clarification = False
    else:
        feedback_type, target_types, needs_clarification = _infer_revision_targets_from_text(
            latest_message,
            artifact_catalog,
        )

    if needs_clarification:
        if reporter:
            reporter.emit("artifact_revision_routing", "success", detail="修改目标不明确，等待用户澄清")
        return Command(goto=ARTIFACT_REVISION_CLARIFICATION_NODE)

    selected_artifacts = [artifact for artifact in artifact_catalog if str(artifact.get("type") or "") in target_types]
    if not selected_artifacts:
        if reporter:
            reporter.emit("artifact_revision_routing", "failed", detail="未找到匹配的产物")
        return Command(
            update={
                "messages": [
                    AIMessage(content="我没有找到与你这次修改要求对应的现有产物。请说明要修改课件、教案还是互动内容。")
                ]
            },
            goto=END,
        )

    if reporter:
        reporter.emit(
            "artifact_revision_routing",
            "success",
            detail="已确定要修改的产物目标",
        )
    update = {
        "user_feedback": latest_message,
        "revision_target_hints": [],
        "feedback_type": feedback_type or "modify_all",
        "revision_targets": selected_artifacts,
        "revision_source_artifacts": selected_artifacts,
        "iteration_count": int(state.get("iteration_count") or 0) + 1,
    }
    update.update(_revision_result_reset_update(selected_artifacts))
    return Command(update=update, goto=ARTIFACT_REVISION_PREPARE_NODE)


_REVISION_MEMORY_SCOPE_PATTERN = re.compile(
    r"(?:学科|科目|主题|课题|年级|学段|受众|学生|对象|教学目标|课程目标|重点|难点|"
    r"subject|topic|grade|audience|objective|key point|difficult)",
    re.IGNORECASE,
)


def _revision_requires_experience_refresh(state: TeachingAssistantState) -> bool:
    return bool(_REVISION_MEMORY_SCOPE_PATTERN.search(str(state.get("user_feedback") or "")))


async def artifact_revision_prepare_node(
    state: TeachingAssistantState,
    config: Optional[RunnableConfig] = None,
    runtime: Runtime[MemoryRuntimeContext] | None = None,
):
    selected_artifacts = state.get("revision_source_artifacts") or []
    include_revision = _revision_requires_experience_refresh(state)
    if state.get("experience_memory_scope_key") and not include_revision:
        bundle = _experience_bundle_from_state(state)
        snapshot_update: dict[str, Any] = {}
        log_observation(
            "memory.experience_snapshot",
            context=run_context_from_config(config, default_run_id="memory").with_agent("memory"),
            sink=observation_sink_from_config(config),
            status="success" if not bundle.degraded else "failed",
            fields={
                "purpose": "artifact_revision",
                "strategy": bundle.strategy,
                "selected_count": bundle.selected_count,
                "truncated": bundle.truncated,
                "reused": True,
                "refreshed": False,
                "degraded": bundle.degraded,
                "degradation_reason": bundle.degradation_reason,
                "duration_ms": bundle.duration_ms,
            },
        )
    else:
        _, snapshot_update = await _ensure_experience_snapshot(
            state,
            request=_artifact_revision_memory_request(state, include_revision=include_revision),
            config=config,
            runtime=runtime,
        )
    goto = _clean_goto_nodes(
        [
            "ppt_revision_node" if any(item.get("type") == "ppt" for item in selected_artifacts) else None,
            "docx_revision_node" if any(item.get("type") == "docx" for item in selected_artifacts) else None,
            "html_game_revision_node" if any(item.get("type") == "html-game" for item in selected_artifacts) else None,
        ]
    )
    return Command(update=snapshot_update, goto=goto or END)


def artifact_revision_clarification_interrupt_node(
    state: TeachingAssistantState,
    config: Optional[RunnableConfig] = None,
):
    reporter = emit_progress(
        config,
        "artifact_revision_routing",
        "running",
        detail="等待用户确认要修改的产物",
    )
    user_input = interrupt(
        _build_approval_payload(
            "artifact_revision_clarification",
            artifact_options=state.get("artifact_catalog") or [],
        )
    )
    if _is_approve_action(user_input):
        selected_artifacts = state.get("artifact_catalog") or []
        if reporter:
            reporter.emit("artifact_revision_routing", "success", detail="将默认修改当前全部产物")
        return Command(
            update={
                "feedback_type": "modify_all",
                "revision_targets": selected_artifacts,
                "revision_source_artifacts": selected_artifacts,
                "user_feedback": _latest_user_message_text(state),
                "iteration_count": int(state.get("iteration_count") or 0) + 1,
                **_revision_result_reset_update(selected_artifacts),
            },
            goto=ARTIFACT_REVISION_PREPARE_NODE,
        )
    return Command(
        update=_build_resume_message_update(user_input),
        goto="artifact_revision_router_node",
    )


def _result_summary_line(result: Mapping[str, Any] | None) -> str | None:
    if not result:
        return None
    artifact_type = str(result.get("artifact_type") or "")
    label = ARTIFACT_TYPE_LABELS.get(artifact_type, artifact_type)
    status = str(result.get("status") or "")
    if status == "ready":
        artifact_id = result.get("artifact_id")
        return f"{label}已完成，请在右侧资料去查看。产物 ID：{artifact_id}"
    if status == "failed":
        error = str(result.get("error") or "未知错误")
        return f"{label}处理失败：{error}"
    return None


async def artifact_fan_in_node(state: TeachingAssistantState, config: Optional[RunnableConfig] = None):
    reporter = emit_progress(config, "artifact_fan_in", "running")
    is_revision = bool(state.get("revision_source_artifacts"))
    if is_revision:
        target_types = [str(artifact.get("type") or "") for artifact in (state.get("revision_source_artifacts") or [])]
    else:
        target_types = _normalize_generation_targets(state.get("generation_targets"))

    results = [
        state.get(result_key)
        for result_key in (_result_key_for_artifact_type(artifact_type) for artifact_type in target_types)
        if result_key
    ]
    summary_lines = [line for line in (_result_summary_line(result) for result in results) if line]
    if not summary_lines:
        return {}

    header = "产物修改结果如下：" if is_revision else "产物生成结果如下："
    finished_results = [
        result for result in results if isinstance(result, Mapping) and result.get("status") in {"ready", "failed"}
    ]
    if reporter:
        reporter.emit("artifact_fan_in", "success", detail="已汇总产物处理结果")
    return {
        "model_workflow_active": False,
        "revision_results": finished_results,
        "messages": [AIMessage(content=header + "\n" + "\n".join(f"- {line}" for line in summary_lines))],
    }


def _clean_goto_nodes(nodes: Sequence[str | None]) -> list[str]:
    return [node for node in nodes if isinstance(node, str) and node]


def build_agent_graph(
    *,
    checkpointer: AsyncPostgresSaver,
    store: BaseStore | None = None,
    rag_runtime: RagRuntime,
    ppt_generate_node: Callable[[TeachingAssistantState, RunnableConfig | None], Awaitable[dict]],
    docx_generate_node: Callable[[TeachingAssistantState, RunnableConfig | None], Awaitable[dict]],
    html_generate_node: Callable[[TeachingAssistantState, RunnableConfig | None], Awaitable[dict]],
    ppt_revision_node: Callable[[TeachingAssistantState, RunnableConfig | None], Awaitable[dict]],
    docx_revision_node: Callable[[TeachingAssistantState, RunnableConfig | None], Awaitable[dict]],
    html_revision_node: Callable[[TeachingAssistantState, RunnableConfig | None], Awaitable[dict]],
):
    async def rag_retrieval_node(
        state: TeachingAssistantState,
        config: Optional[RunnableConfig] = None,
    ):
        reporter = emit_progress(config, "rag_retrieval", "running")
        try:
            query = _build_rag_query(state)
            rag_started_at = time.perf_counter()
            try:
                result = await rag_runtime.retrieval(query, plan_id=state.get("plan_id"))
            except Exception as exc:
                record_metric(
                    "rag.retrieve",
                    context=_get_run_context(config),
                    sink=_get_observation_sink(config),
                    status="failed",
                    duration_ms=int((time.perf_counter() - rag_started_at) * 1000),
                    fields={
                        "plan_id": state.get("plan_id"),
                        "query_size": len(query),
                        "result_count": 0,
                        "error_category": "rag_error",
                        "error_type": exc.__class__.__name__,
                        "error_message": str(exc),
                    },
                )
                raise
            record_metric(
                "rag.retrieve",
                context=_get_run_context(config),
                sink=_get_observation_sink(config),
                status="success",
                duration_ms=int((time.perf_counter() - rag_started_at) * 1000),
                fields={
                    "plan_id": state.get("plan_id"),
                    "query_size": len(query),
                    "result_count": len(result),
                },
            )
            rag_results = [
                {
                    "page_content": document.page_content,
                    "metadata": document.metadata,
                }
                for document in result
            ]
            rag_context = "\n\n".join(document["page_content"] for document in rag_results)
            if reporter:
                reporter.emit(
                    "rag_retrieval",
                    "success",
                    detail=f"已检索到 {len(rag_results)} 条相关内容",
                )
            return {"rag_results": rag_results, "rag_context": rag_context}
        except Exception as exc:
            if reporter:
                reporter.emit("rag_retrieval", "failed", detail=str(exc))
            raise

    async def teaching_context_prepare_node(
        state: TeachingAssistantState,
        config: Optional[RunnableConfig] = None,
        runtime: Runtime[MemoryRuntimeContext] | None = None,
    ):
        async def prepare_rag() -> dict[str, Any]:
            try:
                return await rag_retrieval_node(state, config)
            except Exception:
                return {"rag_results": [], "rag_context": ""}

        async def prepare_experience() -> dict[str, Any]:
            try:
                _, snapshot_update = await _ensure_experience_snapshot(
                    state,
                    request=_teaching_design_memory_request(state),
                    config=config,
                    runtime=runtime,
                )
                return snapshot_update
            except Exception as exc:
                log_observation(
                    "memory.experience_snapshot",
                    context=run_context_from_config(config, default_run_id="memory").with_agent("memory"),
                    sink=observation_sink_from_config(config),
                    status="failed",
                    fields={
                        "purpose": "teaching_design",
                        "strategy": "none",
                        "selected_count": 0,
                        "truncated": False,
                        "reused": False,
                        "refreshed": False,
                        "degraded": True,
                        "degradation_reason": "provider_error",
                        "error_type": exc.__class__.__name__,
                    },
                )
                return {
                    "experience_memory_scope_key": "",
                    "experience_memory_context": "",
                    "experience_memory_selected_ids": [],
                    "experience_memory_strategy": "none",
                    "experience_memory_truncated": False,
                    "experience_memory_degraded": True,
                    "experience_memory_degradation_reason": "provider_error",
                }

        rag_update, experience_update = await asyncio.gather(prepare_rag(), prepare_experience())
        return {**rag_update, **experience_update}

    agent_builder = StateGraph(
        TeachingAssistantState,
        context_schema=MemoryRuntimeContext,
    )
    agent_builder.add_node(
        "profile_memory_load_node", _observed_graph_node("profile_memory_load_node", profile_memory_load_node)
    )
    agent_builder.add_node(
        CONVERSATION_ENTRY_NODE,
        _observed_graph_node(CONVERSATION_ENTRY_NODE, conversation_entry_agent),
        destinations=(TEACHING_INTAKE_NODE, "artifact_revision_router_node", END),
    )
    agent_builder.add_node(
        TEACHING_INTAKE_NODE,
        _observed_graph_node(TEACHING_INTAKE_NODE, teaching_intake_agent),
        destinations=(TEACHING_INTAKE_NODE, INTERRUPT_FOR_USERINPUT_NODE, METADATA_REVIEW_INTERRUPT_NODE, END),
    )
    agent_builder.add_node(INTERRUPT_FOR_USERINPUT_NODE, interrupt_for_userinput)
    agent_builder.add_node(METADATA_REVIEW_INTERRUPT_NODE, metadata_review_interrupt_node)
    agent_builder.add_node("rag_retrieval_node", _observed_graph_node("rag_retrieval_node", rag_retrieval_node))
    agent_builder.add_node(
        TEACHING_CONTEXT_PREPARE_NODE,
        _observed_graph_node(TEACHING_CONTEXT_PREPARE_NODE, teaching_context_prepare_node),
    )
    agent_builder.add_node(
        "teaching_design_planner", _observed_graph_node("teaching_design_planner", teaching_design_planner)
    )
    agent_builder.add_node(TEACHING_PLAN_REVIEW_INTERRUPT_NODE, teaching_plan_review_interrupt_node)
    agent_builder.add_node(
        "artifact_revision_router_node",
        _observed_graph_node("artifact_revision_router_node", artifact_revision_router_node),
    )
    agent_builder.add_node(ARTIFACT_REVISION_CLARIFICATION_NODE, artifact_revision_clarification_interrupt_node)
    agent_builder.add_node(
        ARTIFACT_REVISION_PREPARE_NODE,
        _observed_graph_node(ARTIFACT_REVISION_PREPARE_NODE, artifact_revision_prepare_node),
    )
    agent_builder.add_node("ppt_generate_node", _observed_graph_node("ppt_generate_node", ppt_generate_node))
    agent_builder.add_node("docx_generate_node", _observed_graph_node("docx_generate_node", docx_generate_node))
    agent_builder.add_node(
        "html_game_generate_node", _observed_graph_node("html_game_generate_node", html_generate_node)
    )
    agent_builder.add_node("ppt_revision_node", _observed_graph_node("ppt_revision_node", ppt_revision_node))
    agent_builder.add_node("docx_revision_node", _observed_graph_node("docx_revision_node", docx_revision_node))
    agent_builder.add_node(
        "html_game_revision_node", _observed_graph_node("html_game_revision_node", html_revision_node)
    )
    agent_builder.add_node("artifact_fan_in_node", _observed_graph_node("artifact_fan_in_node", artifact_fan_in_node))

    agent_builder.add_edge(START, "profile_memory_load_node")
    agent_builder.add_edge("profile_memory_load_node", CONVERSATION_ENTRY_NODE)
    agent_builder.add_edge(INTERRUPT_FOR_USERINPUT_NODE, TEACHING_INTAKE_NODE)
    agent_builder.add_edge("rag_retrieval_node", "teaching_design_planner")
    agent_builder.add_edge(TEACHING_CONTEXT_PREPARE_NODE, "teaching_design_planner")
    agent_builder.add_edge("teaching_design_planner", TEACHING_PLAN_REVIEW_INTERRUPT_NODE)
    agent_builder.add_edge("ppt_generate_node", "artifact_fan_in_node")
    agent_builder.add_edge("docx_generate_node", "artifact_fan_in_node")
    agent_builder.add_edge("html_game_generate_node", "artifact_fan_in_node")
    agent_builder.add_edge("ppt_revision_node", "artifact_fan_in_node")
    agent_builder.add_edge("docx_revision_node", "artifact_fan_in_node")
    agent_builder.add_edge("html_game_revision_node", "artifact_fan_in_node")
    agent_builder.add_edge("artifact_fan_in_node", END)

    return agent_builder.compile(checkpointer=checkpointer, store=store)

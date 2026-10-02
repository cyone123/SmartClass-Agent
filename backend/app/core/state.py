from __future__ import annotations

from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TeachingMetadata(TypedDict):
    subject: str | None
    grade: str | None
    topic: str | None
    course_duration: str
    core_points: list[str] | None
    key_points: list[str] | None
    difficult_points: list[str] | None
    teaching_objectives: str | None
    is_complete: bool


class SubAgentResult(TypedDict):
    status: Literal["pending", "running", "ready", "failed"]
    artifact_id: int | None
    artifact_type: Literal["ppt", "docx", "html-game"] | None
    title: str | None
    error: str | None


class TeachingAssistantState(TypedDict):
    model_run_envelope: NotRequired[dict[str, Any]]
    model_config_snapshot: NotRequired[dict[str, Any]]
    model_workflow_id: NotRequired[str | None]
    model_workflow_active: NotRequired[bool]
    model_config_selection: NotRequired[str]
    legacy_snapshot_adopted: NotRequired[bool]
    messages: Annotated[list[BaseMessage], add_messages]
    plan_id: NotRequired[int]
    teaching_metadata: NotRequired[TeachingMetadata | None]
    rag_context: NotRequired[str]
    rag_results: NotRequired[list[dict[str, Any]]]
    profile_memory_loaded: NotRequired[bool]
    profile_memory_context: NotRequired[str]
    profile_memory_item_count: NotRequired[int]
    profile_memory_truncated: NotRequired[bool]
    teaching_task_initial_request: NotRequired[str]
    teaching_task_active: NotRequired[bool]
    teaching_task_scope_id: NotRequired[str]
    teaching_task_start_message_index: NotRequired[int]
    teaching_intake_turn_count: NotRequired[int]
    last_submitted_teaching_metadata: NotRequired[TeachingMetadata | None]
    experience_memory_scope_key: NotRequired[str]
    experience_memory_context: NotRequired[str]
    experience_memory_selected_ids: NotRequired[list[str]]
    experience_memory_strategy: NotRequired[str]
    experience_memory_truncated: NotRequired[bool]
    experience_memory_degraded: NotRequired[bool]
    experience_memory_degradation_reason: NotRequired[str]
    teaching_design_plan: NotRequired[str]
    generation_targets: NotRequired[list[Literal["ppt", "docx", "html-game"]]]
    artifact_catalog: NotRequired[list[dict[str, Any]]]
    ppt_result: NotRequired[SubAgentResult]
    lesson_plan_result: NotRequired[SubAgentResult]
    game_result: NotRequired[SubAgentResult]
    user_feedback: NotRequired[str | None]
    revision_target_hints: NotRequired[list[Literal["ppt", "docx", "html-game"]]]
    feedback_type: NotRequired[
        Literal["approve", "modify_ppt", "modify_lesson_plan", "modify_game", "modify_all"] | None
    ]
    revision_targets: NotRequired[list[dict[str, Any]]]
    revision_source_artifacts: NotRequired[list[dict[str, Any]]]
    revision_results: NotRequired[list[SubAgentResult]]
    iteration_count: NotRequired[int]
    error: NotRequired[str | None]
    retry_count: NotRequired[int]

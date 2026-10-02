from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import (
    get_memory_reflection_experience_snapshot_max_chars,
    get_memory_reflection_profile_snapshot_max_chars,
)
from app.core.memory import sanitize_memory_text
from app.core.model_access.schemas import ResolvedModelConfigSnapshot

MemoryReflectionKind = Literal["profile", "experience"]
MemoryEvidenceType = Literal["new_user_input", "generated_plan", "generated_artifact", "revised_artifact"]
MemoryMutationOperation = Literal["create", "update", "noop"]


def _bounded_text(value: Any, *, limit: int) -> str:
    sanitized = sanitize_memory_text(str(value or ""))
    for pattern, replacement in (
        (r"(?i)authorization\s*:\s*bearer\s+[^\s]+", "Authorization: [已移除]"),
        (r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [已移除]"),
        (r"(?i)https?://[^\s]+", "[已移除 URL]"),
        (r"(?i)(?:s3|minio)://[^\s]+", "[已移除对象键]"),
        (r"(?i)\b[A-Z]:\\[^\r\n]+", "[已移除本机路径]"),
        (r"(?i)(?:/home|/users|/var|/tmp)/[^\s]+", "[已移除本机路径]"),
    ):
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized.strip()[:limit]


class ProfileReflectionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1, 2] = 2
    user_id: str = Field(max_length=128)
    model_config_snapshot: ResolvedModelConfigSnapshot | None = None
    legacy_snapshot_adopted: bool = False
    source_run_id: str = Field(max_length=64)
    source_thread_id: str = Field(max_length=255)
    business_stage: str = Field(max_length=48)
    captured_at: datetime
    user_input: str
    evidence_type: Literal["new_user_input"] = "new_user_input"

    @field_validator("user_input", mode="before")
    @classmethod
    def bound_user_input(cls, value: Any) -> str:
        return _bounded_text(value, limit=get_memory_reflection_profile_snapshot_max_chars())


class ExperienceReflectionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1, 2] = 2
    user_id: str = Field(max_length=128)
    model_config_snapshot: ResolvedModelConfigSnapshot | None = None
    legacy_snapshot_adopted: bool = False
    source_run_id: str = Field(max_length=64)
    source_thread_id: str = Field(max_length=255)
    source_plan_id: int | None = None
    business_stage: str = Field(max_length=48)
    captured_at: datetime
    evidence_type: Literal["generated_plan", "generated_artifact", "revised_artifact"]
    outcome_summary: str
    teaching_metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("outcome_summary", mode="before")
    @classmethod
    def bound_outcome(cls, value: Any) -> str:
        return _bounded_text(value, limit=get_memory_reflection_experience_snapshot_max_chars())

    @field_validator("teaching_metadata", mode="before")
    @classmethod
    def allow_metadata_fields(cls, value: Any) -> dict[str, Any]:
        allowed = {
            "subject",
            "grade",
            "topic",
            "course_duration",
            "teaching_objectives",
            "language",
        }
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, Any] = {}
        for key in sorted(allowed.intersection(value)):
            item = value[key]
            if isinstance(item, (str, int, float, bool)) or item is None:
                normalized[key] = _bounded_text(item, limit=500) if isinstance(item, str) else item
        return normalized


class MemoryMutationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    operation: MemoryMutationOperation
    kind: MemoryReflectionKind
    target_memory_id: str | None = Field(default=None, max_length=64)
    base_version: int | None = Field(default=None, ge=0)
    title: str = Field(default="", max_length=240)
    summary: str = Field(default="", max_length=1000)
    content: str = Field(default="", max_length=6000)
    tags: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("title", "summary", "content", mode="before")
    @classmethod
    def sanitize_text(cls, value: Any) -> str:
        return sanitize_memory_text(str(value or ""))

    @field_validator("tags", mode="before")
    @classmethod
    def sanitize_tags(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [sanitize_memory_text(str(item))[:80] for item in value if sanitize_memory_text(str(item))][:8]


ReflectionSnapshot = ProfileReflectionSnapshot | ExperienceReflectionSnapshot

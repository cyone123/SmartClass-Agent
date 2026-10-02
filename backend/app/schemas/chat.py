from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ApprovalActionRequest(BaseModel):
    action: Literal["approve"] = Field(..., description="Approval action")
    interrupt_id: str = Field(..., min_length=1, description="Pending interrupt id")
    selected_artifact_types: Optional[list[Literal["ppt", "docx", "html-game"]]] = Field(
        default=None,
        description="Selected artifact types for teaching plan approval",
    )


class ChatRequest(BaseModel):
    message: Optional[str] = Field(None, description="User input message")
    thread_id: Optional[str] = Field(None, description="Conversation thread id")
    attachment_ids: Optional[list[int]] = Field(
        default=None,
        description="Attachment ids for the current message",
    )
    approval: Optional[ApprovalActionRequest] = Field(
        default=None,
        description="Approval action payload for resuming an approval interrupt",
    )
    temperature: Optional[float] = Field(0.7, description="Sampling temperature")
    stream: Optional[bool] = Field(False, description="Whether to stream the response")

    @model_validator(mode="after")
    def validate_payload(self) -> "ChatRequest":
        has_message = bool((self.message or "").strip())
        if self.approval is None and not has_message:
            raise ValueError("message is required when approval is not provided.")
        if self.approval is not None and not self.thread_id:
            raise ValueError("thread_id is required when approval is provided.")
        return self


class ChatResponse(BaseModel):
    thread_id: str
    response: str
    tokens_used: Optional[int] = None
    processing_time: float


ChatRunStatus = Literal[
    "queued",
    "running",
    "waiting_approval",
    "succeeded",
    "failed",
    "cancelled",
]


class ChatRunSnapshot(BaseModel):
    run_id: str
    thread_id: str
    plan_id: int
    status: ChatRunStatus
    output_text: str = ""
    last_event_sequence: int = 0
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ChatRunLookupResponse(BaseModel):
    run: ChatRunSnapshot | None = None


class ChatRunEventSnapshot(BaseModel):
    run_id: str
    sequence: int
    event: str
    data: dict[str, Any]
    created_at: datetime

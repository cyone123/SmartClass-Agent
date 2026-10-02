from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MemoryReflectionJob(Base):
    __tablename__ = "memory_reflection_jobs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_run_id",
            "kind",
            "business_stage",
            "extractor_version",
            name="uq_memory_reflection_job_idempotency",
        ),
        Index("ix_memory_reflection_jobs_pending", "status", "created_at"),
    )

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    business_stage: Mapped[str] = mapped_column(String(48), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    error_category: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_memory_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    applied_memory_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MemoryMutationGuard(Base):
    __tablename__ = "memory_mutation_guards"
    __table_args__ = (UniqueConstraint("user_id", "kind", "memory_id", name="uq_memory_mutation_guard_target"),)

    guard_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    memory_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deletion_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_manual_mutation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_applied_job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

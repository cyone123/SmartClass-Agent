from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_memory_reflection_evaluation_timeout_seconds, get_memory_reflection_terminal_retention_days
from app.core.model_access import current_snapshot
from app.core.model_access.schemas import restore_snapshot
from app.core.model_access.workflow import restore_envelope
from app.core.observability import RunContext, get_observation_sink, log_observation, record_metric
from app.models.memory_reflection import MemoryReflectionJob
from app.schemas.memory_reflection import ExperienceReflectionSnapshot, ProfileReflectionSnapshot, ReflectionSnapshot

JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_SUCCEEDED = "succeeded"
JOB_SKIPPED = "skipped"
JOB_FAILED = "failed"
JOB_TERMINAL = (JOB_SUCCEEDED, JOB_SKIPPED, JOB_FAILED)
JOB_EXTRACTOR_VERSION = "v1"


@dataclass(frozen=True)
class ReflectionJobCandidate:
    kind: str
    business_stage: str
    extractor_version: str
    snapshot: ReflectionSnapshot


def _compact_json(value: Any, *, limit: int) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return encoded[:limit]


def build_reflection_job_candidates(
    *,
    run: Any,
    status: str,
    checkpoint_values: dict[str, Any] | None,
) -> list[ReflectionJobCandidate]:
    """Build immutable, allowlisted evidence without model or Store access."""
    if status not in {"waiting_approval", "succeeded"}:
        return []
    candidates: list[ReflectionJobCandidate] = []
    model_config = (checkpoint_values or {}).get("model_config_snapshot")
    envelope = getattr(run, "model_config_snapshot", None)
    model_snapshot = (
        restore_snapshot(model_config)
        if model_config
        else restore_envelope(envelope).selected()
        if envelope
        else current_snapshot()
    )
    is_approval_resume = bool(getattr(run, "approval", None))
    message = str(getattr(run, "message", "") or "").strip()
    if message and not is_approval_resume:
        profile = ProfileReflectionSnapshot(
            model_config_snapshot=model_snapshot,
            user_id=str(run.user_id),
            source_run_id=str(run.run_id),
            source_thread_id=str(run.thread_id),
            business_stage=status,
            captured_at=datetime.now(UTC),
            user_input=message,
        )
        candidates.append(
            ReflectionJobCandidate(
                kind="profile",
                business_stage=status,
                extractor_version=JOB_EXTRACTOR_VERSION,
                snapshot=profile,
            )
        )
    if status != "succeeded" or not checkpoint_values:
        return candidates

    intent = str(checkpoint_values.get("intent") or "")
    if intent not in {"teaching_plan", "artifact_revision"}:
        return candidates

    results = [
        item
        for item in checkpoint_values.get("revision_results", []) or []
        if isinstance(item, dict) and item.get("status") == "ready"
    ]
    is_revision = bool(checkpoint_values.get("revision_source_artifacts"))
    plan_text = str(checkpoint_values.get("teaching_design_plan") or "").strip()
    if results:
        evidence_type = "revised_artifact" if is_revision else "generated_artifact"
        outcome = _compact_json(
            {
                "teaching_design_plan": plan_text,
                "revision_request": str(checkpoint_values.get("user_feedback") or "") if is_revision else "",
                "artifacts": [
                    {
                        "status": item.get("status"),
                        "artifact_type": item.get("artifact_type"),
                        "title": item.get("title"),
                    }
                    for item in results
                ],
            },
            limit=12000,
        )
    elif intent == "teaching_plan" and plan_text:
        evidence_type = "generated_plan"
        outcome = plan_text
    else:
        return candidates

    metadata = checkpoint_values.get("teaching_metadata")
    experience = ExperienceReflectionSnapshot(
        model_config_snapshot=model_snapshot,
        user_id=str(run.user_id),
        source_run_id=str(run.run_id),
        source_thread_id=str(run.thread_id),
        source_plan_id=getattr(run, "plan_id", None),
        business_stage="artifact_revision" if is_revision else "teaching_outcome",
        captured_at=datetime.now(UTC),
        evidence_type=evidence_type,
        outcome_summary=outcome,
        teaching_metadata=metadata if isinstance(metadata, dict) else {},
    )
    candidates.append(
        ReflectionJobCandidate(
            kind="experience",
            business_stage=experience.business_stage,
            extractor_version=JOB_EXTRACTOR_VERSION,
            snapshot=experience,
        )
    )
    return candidates


async def register_reflection_candidates(
    db: AsyncSession,
    candidates: Iterable[ReflectionJobCandidate],
) -> list[MemoryReflectionJob]:
    rows: list[MemoryReflectionJob] = []
    for candidate in candidates:
        snapshot = candidate.snapshot
        lookup = select(MemoryReflectionJob).where(
            MemoryReflectionJob.user_id == snapshot.user_id,
            MemoryReflectionJob.source_run_id == snapshot.source_run_id,
            MemoryReflectionJob.kind == candidate.kind,
            MemoryReflectionJob.business_stage == candidate.business_stage,
            MemoryReflectionJob.extractor_version == candidate.extractor_version,
        )
        existing = (await db.execute(lookup)).scalar_one_or_none()
        if existing is not None:
            rows.append(existing)
            continue
        values = {
            "job_id": uuid4().hex,
            "user_id": snapshot.user_id,
            "source_run_id": snapshot.source_run_id,
            "source_thread_id": snapshot.source_thread_id,
            "source_plan_id": getattr(snapshot, "source_plan_id", None),
            "kind": candidate.kind,
            "business_stage": candidate.business_stage,
            "extractor_version": candidate.extractor_version,
            "snapshot_version": snapshot.schema_version,
            "snapshot": snapshot.model_dump(mode="json"),
            "evidence_type": snapshot.evidence_type,
            "status": JOB_PENDING,
        }
        dialect_name = db.get_bind().dialect.name
        created = True
        if dialect_name == "postgresql":
            insert_statement = (
                pg_insert(MemoryReflectionJob)
                .values(**values)
                .on_conflict_do_nothing(constraint="uq_memory_reflection_job_idempotency")
            )
        elif dialect_name == "sqlite":
            insert_statement = (
                sqlite_insert(MemoryReflectionJob)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=["user_id", "source_run_id", "kind", "business_stage", "extractor_version"]
                )
            )
        else:
            row = MemoryReflectionJob(**values)
            db.add(row)
            await db.flush()
            rows.append(row)
        if dialect_name in {"postgresql", "sqlite"}:
            result = await db.execute(insert_statement)
            created = result.rowcount == 1
            row = (await db.execute(lookup)).scalar_one()
            rows.append(row)
        if not created:
            continue
        context = RunContext(
            run_id=snapshot.source_run_id,
            thread_id=snapshot.source_thread_id,
            plan_id=getattr(snapshot, "source_plan_id", None),
            user_id=str(snapshot.user_id),
            agent_name="memory_scheduler",
        )
        log_observation(
            "memory.reflection.registered",
            context=context,
            sink=get_observation_sink(),
            status="success",
            fields={"job_kind": candidate.kind, "job_state": row.status},
        )
        record_metric(
            "memory.reflection.job",
            context=context,
            sink=get_observation_sink(),
            status="success",
            fields={"job_kind": candidate.kind, "job_state": row.status},
        )
    return rows


class MemoryReflectionJobRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def take_next(self) -> MemoryReflectionJob | None:
        next_job_id = (
            select(MemoryReflectionJob.job_id)
            .where(MemoryReflectionJob.status == JOB_PENDING)
            .order_by(MemoryReflectionJob.created_at.asc())
            .limit(1)
            .scalar_subquery()
        )
        statement = (
            update(MemoryReflectionJob)
            .where(
                MemoryReflectionJob.job_id == next_job_id,
                MemoryReflectionJob.status == JOB_PENDING,
            )
            .values(status=JOB_RUNNING, error_category=None, error_message=None)
            .returning(MemoryReflectionJob)
        )
        row = (await self.db.execute(statement)).scalar_one_or_none()
        await self.db.commit()
        return row

    async def queue_depth(self) -> int:
        value = await self.db.scalar(
            select(func.count())
            .select_from(MemoryReflectionJob)
            .where(MemoryReflectionJob.status.in_((JOB_PENDING, JOB_RUNNING)))
        )
        return int(value or 0)

    async def succeed(self, job_id: str, *, memory_id: str | None, memory_version: int | None) -> None:
        await self._finish(job_id, JOB_SUCCEEDED, memory_id=memory_id, memory_version=memory_version)

    async def skip(self, job_id: str, *, category: str = "policy_skip") -> None:
        await self._finish(job_id, JOB_SKIPPED, error_category=category)

    async def fail(
        self,
        job_id: str,
        *,
        category: str,
        message: str = "Background memory reflection failed.",
    ) -> None:
        row = await self.db.get(MemoryReflectionJob, job_id, with_for_update=True)
        if row is None or row.status != JOB_RUNNING:
            return
        safe_category = category[:48] if category else "unknown_error"
        row.error_category = safe_category
        row.error_message = message[:500]
        row.status = JOB_FAILED
        row.completed_at = datetime.now(UTC)
        await self.db.commit()

    async def fail_interrupted(self) -> list[str]:
        statement = (
            update(MemoryReflectionJob)
            .where(MemoryReflectionJob.status == JOB_RUNNING)
            .values(
                status=JOB_FAILED,
                error_category="worker_interrupted",
                error_message="Background memory reflection was interrupted by process shutdown.",
                completed_at=datetime.now(UTC),
            )
            .returning(MemoryReflectionJob.kind)
        )
        kinds = list((await self.db.execute(statement)).scalars().all())
        await self.db.commit()
        return kinds

    async def _finish(
        self,
        job_id: str,
        status: str,
        *,
        memory_id: str | None = None,
        memory_version: int | None = None,
        error_category: str | None = None,
    ) -> None:
        row = await self.db.get(MemoryReflectionJob, job_id, with_for_update=True)
        if row is None or row.status != JOB_RUNNING:
            return
        row.status = status
        row.applied_memory_id = memory_id
        row.applied_memory_version = memory_version
        row.error_category = error_category
        row.error_message = None
        row.completed_at = datetime.now(UTC)
        await self.db.commit()

    async def cleanup_terminal(self, *, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now(UTC)) - timedelta(days=get_memory_reflection_terminal_retention_days())
        result = await self.db.execute(
            delete(MemoryReflectionJob).where(
                MemoryReflectionJob.status.in_(JOB_TERMINAL), MemoryReflectionJob.completed_at < cutoff
            )
        )
        await self.db.commit()
        return int(result.rowcount or 0)


async def wait_for_source_run_jobs(
    session_factory: Any,
    source_run_id: str,
    *,
    timeout_seconds: float | None = None,
    poll_seconds: float = 0.1,
) -> list[MemoryReflectionJob]:
    deadline = asyncio.get_running_loop().time() + (
        timeout_seconds if timeout_seconds is not None else get_memory_reflection_evaluation_timeout_seconds()
    )
    while True:
        async with session_factory() as db:
            rows = list(
                (
                    await db.execute(
                        select(MemoryReflectionJob).where(MemoryReflectionJob.source_run_id == source_run_id)
                    )
                )
                .scalars()
                .all()
            )
        if rows and all(row.status in JOB_TERMINAL for row in rows):
            return rows
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(f"Timed out waiting for memory reflection jobs for source run {source_run_id}.")
        await asyncio.sleep(poll_seconds)

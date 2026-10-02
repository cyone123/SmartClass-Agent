from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_access.workflow import capture_envelope, restore_envelope
from app.models.agent_run import AgentRun
from app.models.session import Session
from app.services.memory_reflection_service import ReflectionJobCandidate, register_reflection_candidates

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_WAITING_APPROVAL = "waiting_approval"
RUN_STATUS_SUCCEEDED = "succeeded"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"

ACTIVE_RUN_STATUSES = (RUN_STATUS_QUEUED, RUN_STATUS_RUNNING)
FINISHED_RUN_STATUSES = (
    RUN_STATUS_WAITING_APPROVAL,
    RUN_STATUS_SUCCEEDED,
    RUN_STATUS_FAILED,
    RUN_STATUS_CANCELLED,
)
SUPPORTED_RUN_EVENTS = {
    "metadata",
    "progress",
    "token",
    "artifact",
    "artifact_trace",
    "approval",
    "suggestions",
    "error",
    "done",
}
STALE_RUN_ERROR_MESSAGE = "服务重启，本轮运行未能继续。请重新发送。"


class ActiveChatRunConflictError(RuntimeError):
    def __init__(self, run: AgentRun) -> None:
        super().__init__(f"Thread {run.thread_id} already has active run {run.run_id}.")
        self.run = run


def serialize_chat_run(run: AgentRun, *, live_snapshot: Any | None = None) -> dict[str, Any]:
    use_live_projection = run.status in ACTIVE_RUN_STATUSES and live_snapshot is not None
    return {
        "run_id": run.run_id,
        "thread_id": run.thread_id,
        "plan_id": run.plan_id,
        "status": run.status,
        "output_text": live_snapshot.output_text if use_live_projection else run.output_text or "",
        "last_event_sequence": live_snapshot.last_sequence if use_live_projection else run.last_event_sequence or 0,
        "error_message": run.error_message,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


async def create_chat_run(
    db: AsyncSession,
    *,
    thread_id: str,
    user_id: int,
    plan_id: int,
    message: str,
    attachment_ids: list[int],
    approval: dict[str, Any] | None,
    workflow_state: dict[str, Any] | None = None,
) -> AgentRun:
    session_stmt = select(Session).where(Session.thread_id == thread_id, Session.user_id == user_id).with_for_update()
    owned_session = (await db.execute(session_stmt)).scalar_one_or_none()
    if owned_session is None:
        raise ValueError(f"Thread {thread_id} not found.")

    active_stmt = (
        select(AgentRun)
        .where(
            AgentRun.thread_id == thread_id,
            AgentRun.user_id == user_id,
            AgentRun.status.in_(ACTIVE_RUN_STATUSES),
        )
        .order_by(AgentRun.created_at.desc())
    )
    active_run = (await db.execute(active_stmt)).scalars().first()
    if active_run is not None:
        raise ActiveChatRunConflictError(active_run)

    # A process may stop after durable acceptance and before the first graph checkpoint.
    # Recover a legacy workflow's already accepted identity from its previous run.
    workflow_state = dict(workflow_state or {})
    if workflow_state.get(
        "model_workflow_active", workflow_state.get("teaching_task_active", False)
    ) and not workflow_state.get("model_config_snapshot"):
        previous = (
            (
                await db.execute(
                    select(AgentRun)
                    .where(AgentRun.thread_id == thread_id, AgentRun.user_id == user_id)
                    .order_by(AgentRun.created_at.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if previous is not None and previous.status != RUN_STATUS_CANCELLED and previous.model_config_snapshot:
            accepted = restore_envelope(previous.model_config_snapshot)
            if accepted.workflow is not None:
                workflow_state.update(
                    model_config_snapshot=accepted.workflow.model_dump(mode="json"),
                    model_workflow_id=accepted.workflow_id,
                    legacy_snapshot_adopted=accepted.legacy_snapshot_adopted,
                )

    run = AgentRun(
        run_id=uuid4().hex,
        thread_id=thread_id,
        user_id=user_id,
        plan_id=plan_id,
        status=RUN_STATUS_QUEUED,
        message=message,
        attachment_ids=list(attachment_ids),
        approval=approval,
        model_config_snapshot=capture_envelope(workflow_state).model_dump(mode="json"),
        output_text="",
        last_event_sequence=0,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def adopt_model_snapshot(db: AsyncSession, run: AgentRun, workflow_state: dict | None = None) -> dict:
    if run.model_config_snapshot is None:
        run.model_config_snapshot = capture_envelope(workflow_state, legacy=True).model_dump(mode="json")
        try:
            await db.commit()
        except Exception:
            run.model_config_snapshot = None
            raise
        await db.refresh(run)
    return restore_envelope(run.model_config_snapshot).model_dump(mode="json")


async def get_chat_run(db: AsyncSession, run_id: str) -> AgentRun | None:
    return await db.get(AgentRun, run_id)


async def get_owned_chat_run(db: AsyncSession, run_id: str, *, user_id: int) -> AgentRun | None:
    stmt = select(AgentRun).where(AgentRun.run_id == run_id, AgentRun.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_active_chat_run(
    db: AsyncSession,
    *,
    thread_id: str,
    user_id: int,
) -> AgentRun | None:
    stmt = (
        select(AgentRun)
        .where(
            AgentRun.thread_id == thread_id,
            AgentRun.user_id == user_id,
            AgentRun.status.in_(ACTIVE_RUN_STATUSES),
        )
        .order_by(AgentRun.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().first()


async def mark_chat_run_running(db: AsyncSession, run_id: str) -> AgentRun | None:
    stmt = select(AgentRun).where(AgentRun.run_id == run_id).with_for_update()
    run = (await db.execute(stmt)).scalar_one_or_none()
    if run is None:
        return None
    if run.status == RUN_STATUS_QUEUED:
        run.status = RUN_STATUS_RUNNING
        run.started_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(run)
    return run


async def finalize_chat_run(
    db: AsyncSession,
    *,
    run_id: str,
    status: str,
    output_text: str,
    last_sequence: int,
    error_message: str | None = None,
    reflection_candidates: list[ReflectionJobCandidate] | None = None,
) -> AgentRun | None:
    if status not in FINISHED_RUN_STATUSES:
        raise ValueError(f"Invalid terminal chat run status: {status}")
    stmt = select(AgentRun).where(AgentRun.run_id == run_id).with_for_update()
    run = (await db.execute(stmt)).scalar_one_or_none()
    if run is None:
        return None
    if run.status in FINISHED_RUN_STATUSES:
        return run

    run.status = status
    run.output_text = output_text
    run.last_event_sequence = max(last_sequence, 0) + 1
    run.error_message = error_message
    run.completed_at = datetime.now(timezone.utc)
    if reflection_candidates:
        await register_reflection_candidates(db, reflection_candidates)
    await db.commit()
    await db.refresh(run)
    return run


async def list_stale_chat_runs(db: AsyncSession) -> list[AgentRun]:
    stmt = select(AgentRun).where(AgentRun.status.in_(ACTIVE_RUN_STATUSES)).order_by(AgentRun.created_at.asc())
    return list((await db.execute(stmt)).scalars().all())

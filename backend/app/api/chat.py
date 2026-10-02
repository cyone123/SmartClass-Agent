import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent import AgentRuntime, get_agent_runtime
from app.core.auth import get_current_user
from app.core.chat_run_events import (
    ChatRunEventStoreError,
    ChatRunEventStoreUnavailable,
    ChatRunRedis,
    get_chat_run_redis,
)
from app.core.chat_runs import ChatRunManager, get_chat_run_manager
from app.core.observability import (
    RunContext,
    get_observation_sink,
    log_observation,
)
from app.dependencies.db import AsyncSessionLocal, get_db
from app.models.file import AttachmentFile
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatRunLookupResponse, ChatRunSnapshot
from app.services import chat_run_service, file_service, session_service

router = APIRouter()


def format_sse_event(data: str, *, event: str | None = None, event_id: int | None = None) -> str:
    payload = ""
    if event_id is not None:
        payload += f"id: {event_id}\n"
    if event:
        payload += f"event: {event}\n"
    normalized_data = data.replace("\r\n", "\n").replace("\r", "\n")
    for line in normalized_data.split("\n") or [normalized_data]:
        payload += f"data: {line}\n"
    return payload + "\n"


def format_sse_json_event(payload: object, *, event: str, event_id: int | None = None) -> str:
    return format_sse_event(
        json.dumps(jsonable_encoder(payload), ensure_ascii=False),
        event=event,
        event_id=event_id,
    )


async def _live_snapshot_or_503(event_store: ChatRunRedis, run_id: str):
    try:
        return await event_store.get_snapshot(run_id)
    except ChatRunEventStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat run event storage is unavailable.",
        ) from exc


@router.post("/chat/runs", response_model=ChatRunSnapshot, status_code=status.HTTP_202_ACCEPTED)
async def create_chat_run(
    message: ChatRequest,
    current_user: User = Depends(get_current_user),
    agent_runtime: AgentRuntime = Depends(get_agent_runtime),
    manager: ChatRunManager = Depends(get_chat_run_manager),
    event_store: ChatRunRedis = Depends(get_chat_run_redis),
    db: AsyncSession = Depends(get_db),
):
    thread_id = (message.thread_id or "").strip()
    if not thread_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id is required for durable chat runs.",
        )

    session = await session_service.get_session_by_thread_id(db, thread_id, user_id=current_user.id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread {thread_id} not found.",
        )

    attachment_ids = message.attachment_ids or []
    if attachment_ids:
        await file_service.get_chat_attachments_by_ids(
            db,
            plan_id=session.plan_id,
            thread_id=thread_id,
            attachment_ids=attachment_ids,
            user_id=current_user.id,
        )

    approval = message.approval.model_dump() if message.approval is not None else None
    if approval:
        try:
            await agent_runtime.validate_approval_request(thread_id, approval["interrupt_id"])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    try:
        await event_store.ensure_ready()
    except ChatRunEventStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat run event storage is unavailable.",
        ) from exc

    try:
        run = await chat_run_service.create_chat_run(
            db,
            thread_id=thread_id,
            user_id=current_user.id,
            plan_id=session.plan_id,
            message=message.message or "",
            attachment_ids=attachment_ids,
            approval=approval,
            workflow_state=await agent_runtime.get_memory_reflection_checkpoint_values(thread_id),
        )
    except chat_run_service.ActiveChatRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This thread already has an active run.",
                "run": jsonable_encoder(chat_run_service.serialize_chat_run(exc.run)),
            },
        ) from exc

    try:
        manager.schedule(run.run_id)
    except RuntimeError as exc:
        finalized = await chat_run_service.finalize_chat_run(
            db,
            run_id=run.run_id,
            status=chat_run_service.RUN_STATUS_FAILED,
            output_text="",
            last_sequence=0,
            error_message="对话运行服务暂不可用。",
        )
        if finalized is not None:
            try:
                await event_store.append_done(
                    run.run_id,
                    sequence=finalized.last_event_sequence,
                    status=finalized.status,
                )
            except ChatRunEventStoreError:
                pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat run service is unavailable.",
        ) from exc
    return chat_run_service.serialize_chat_run(run)


@router.get("/chat/runs/active", response_model=ChatRunLookupResponse)
async def get_active_chat_run(
    thread_id: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    event_store: ChatRunRedis = Depends(get_chat_run_redis),
    db: AsyncSession = Depends(get_db),
):
    await session_service.ensure_owned_session_by_thread_id(db, thread_id, user_id=current_user.id)
    run = await chat_run_service.get_active_chat_run(db, thread_id=thread_id, user_id=current_user.id)
    if run is None:
        return {"run": None}
    snapshot = await _live_snapshot_or_503(event_store, run.run_id)
    return {"run": chat_run_service.serialize_chat_run(run, live_snapshot=snapshot)}


@router.get("/chat/runs/{run_id}", response_model=ChatRunSnapshot)
async def get_chat_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    event_store: ChatRunRedis = Depends(get_chat_run_redis),
    db: AsyncSession = Depends(get_db),
):
    run = await chat_run_service.get_owned_chat_run(db, run_id, user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found.")
    snapshot = (
        await _live_snapshot_or_503(event_store, run.run_id)
        if run.status in chat_run_service.ACTIVE_RUN_STATUSES
        else None
    )
    return chat_run_service.serialize_chat_run(run, live_snapshot=snapshot)


@router.post("/chat/runs/{run_id}/cancel", response_model=ChatRunSnapshot)
async def cancel_chat_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    manager: ChatRunManager = Depends(get_chat_run_manager),
    event_store: ChatRunRedis = Depends(get_chat_run_redis),
    db: AsyncSession = Depends(get_db),
):
    run = await chat_run_service.get_owned_chat_run(db, run_id, user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found.")
    if run.status in chat_run_service.ACTIVE_RUN_STATUSES:
        await manager.cancel(run_id)
        await db.rollback()
        run = await chat_run_service.get_owned_chat_run(db, run_id, user_id=current_user.id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found.")
    snapshot = (
        await _live_snapshot_or_503(event_store, run.run_id)
        if run.status in chat_run_service.ACTIVE_RUN_STATUSES
        else None
    )
    return chat_run_service.serialize_chat_run(run, live_snapshot=snapshot)


@router.get("/chat/runs/{run_id}/events")
async def stream_chat_run_events(
    run_id: str,
    after_sequence: int = Query(0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    current_user: User = Depends(get_current_user),
    event_store: ChatRunRedis = Depends(get_chat_run_redis),
    db: AsyncSession = Depends(get_db),
):
    run = await chat_run_service.get_owned_chat_run(db, run_id, user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found.")
    try:
        await event_store.ensure_ready()
    except ChatRunEventStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat run event storage is unavailable.",
        ) from exc

    cursor = after_sequence
    if last_event_id:
        try:
            cursor = max(cursor, int(last_event_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Last-Event-ID must be an integer event sequence.",
            ) from exc

    run_context = RunContext(
        run_id=run.run_id,
        thread_id=run.thread_id,
        plan_id=run.plan_id,
        user_id=str(run.user_id),
        agent_name="chat_run_subscription",
    )
    observation_sink = get_observation_sink()

    async def event_stream():
        current_sequence = cursor
        outcome = "disconnected"
        log_observation(
            "chat.subscription.opened",
            context=run_context,
            sink=observation_sink,
            status="running",
            fields={"resume": current_sequence > 0},
        )
        try:
            while True:
                events = await event_store.read_after(run_id, current_sequence)

                for stored_event in events:
                    current_sequence = stored_event.sequence
                    yield format_sse_json_event(
                        stored_event.payload,
                        event=stored_event.event_type,
                        event_id=stored_event.sequence,
                    )
                    if stored_event.event_type == "done":
                        outcome = "completed"
                        return

                if events:
                    continue

                async with AsyncSessionLocal() as stream_db:
                    current_run = await chat_run_service.get_chat_run(stream_db, run_id)
                if current_run is not None and current_run.status in chat_run_service.FINISHED_RUN_STATUSES:
                    if current_sequence < current_run.last_event_sequence:
                        current_sequence = current_run.last_event_sequence
                        yield format_sse_json_event(
                            {"run_id": run_id, "status": current_run.status},
                            event="done",
                            event_id=current_sequence,
                        )
                    outcome = "completed"
                    return
                yield ": keep-alive\n\n"
        except ChatRunEventStoreError:
            outcome = "transport_failed"
            return
        except asyncio.CancelledError:
            raise
        finally:
            log_observation(
                f"chat.subscription.{outcome}",
                context=run_context,
                sink=observation_sink,
                status="success",
                fields={"outcome": outcome},
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Thread-ID": run.thread_id,
            "X-Run-ID": run.run_id,
        },
    )


@router.post("/chat/stream")
async def chat(
    message: ChatRequest,
    current_user: User = Depends(get_current_user),
    agent_runtime: AgentRuntime = Depends(get_agent_runtime),
    db: AsyncSession = Depends(get_db),
):
    thread_id = message.thread_id
    attachment_ids = message.attachment_ids or []
    approval = message.approval.model_dump() if message.approval is not None else None
    if attachment_ids and not thread_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id is required when attachment_ids are provided.",
        )
    if approval and not thread_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id is required when approval is provided.",
        )

    plan_id = None
    attachments: list[AttachmentFile] | None = None
    if thread_id:
        session = await session_service.get_session_by_thread_id(db, thread_id, user_id=current_user.id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thread {thread_id} not found.",
            )
        plan_id = session.plan_id

    if attachment_ids:
        if plan_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thread {thread_id} not found.",
            )
        attachments = await file_service.get_chat_attachments_by_ids(
            db,
            plan_id=plan_id,
            thread_id=thread_id,
            attachment_ids=attachment_ids,
            user_id=current_user.id,
        )

    if approval:
        try:
            await agent_runtime.validate_approval_request(thread_id, approval["interrupt_id"])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    async def event_stream():
        run_id = uuid4().hex
        run_context = RunContext(
            run_id=run_id,
            thread_id=thread_id,
            plan_id=plan_id,
            user_id=str(current_user.id),
            agent_name="chat_stream",
        )
        observation_sink = get_observation_sink()
        yield format_sse_json_event(
            {"thread_id": thread_id, "run_id": run_id},
            event="metadata",
        )

        log_observation(
            "chat.stream.request",
            context=run_context,
            sink=observation_sink,
            status="running",
            fields={
                "message_size": len(message.message or ""),
                "attachment_count": len(attachment_ids),
                "has_approval": bool(approval),
            },
        )
        try:
            async for event in agent_runtime.stream_agent_events(
                message.message or "",
                thread_id,
                run_id=run_id,
                user_id=str(current_user.id),
                plan_id=plan_id,
                attachments=attachments,
                approval=approval,
                run_context=run_context,
                observation_sink=observation_sink,
            ):
                event_name = event.get("event")
                payload = event.get("data")

                if event_name in {
                    "progress",
                    "token",
                    "error",
                    "suggestions",
                    "artifact",
                    "artifact_trace",
                    "approval",
                }:
                    yield format_sse_json_event(payload, event=event_name)
            log_observation(
                "chat.stream.completed",
                context=run_context,
                sink=observation_sink,
                status="success",
            )
        except Exception as exc:
            log_observation(
                "chat.stream.failed",
                context=run_context,
                sink=observation_sink,
                status="failed",
                fields={
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc),
                },
            )
            yield format_sse_json_event(
                {"run_id": run_id, "message": "对话处理失败，请稍后重试。"},
                event="error",
            )

        yield format_sse_event("[DONE]", event="done")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Thread-ID": thread_id or "",
        },
    )

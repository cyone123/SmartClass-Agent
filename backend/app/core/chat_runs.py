from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any, Awaitable, Callable

from fastapi import Request

from app.config import get_redis_token_batch_interval_ms, get_redis_token_batch_max_chars
from app.core.agent import AgentRuntime
from app.core.chat_run_events import ChatRunEventStoreError, ChatRunRedis
from app.core.observability import RunContext, categorize_error, get_observation_sink, log_observation, record_metric
from app.dependencies.db import AsyncSessionLocal
from app.services import chat_run_service, file_service
from app.services.memory_reflection_service import build_reflection_job_candidates


class _RunPublisher:
    def __init__(self, event_store: ChatRunRedis, run_id: str) -> None:
        self.event_store = event_store
        self.run_id = run_id
        self.last_sequence = 0
        self._lock = asyncio.Lock()

    async def publish(self, event_type: str, payload: dict[str, Any]) -> int:
        async with self._lock:
            sequence = await self.event_store.append(self.run_id, event_type, payload)
            self.last_sequence = sequence
            return sequence


class _TokenEventBuffer:
    def __init__(
        self,
        run_id: str,
        publish: Callable[[str, dict[str, Any]], Awaitable[int]],
        *,
        interval_ms: int,
        max_chars: int,
    ) -> None:
        self.run_id = run_id
        self.publish = publish
        self.interval_seconds = interval_ms / 1000
        self.max_chars = max_chars
        self._fragments: list[str] = []
        self._characters = 0
        self._lock = asyncio.Lock()
        self._timer: asyncio.Task[None] | None = None
        self._failure: BaseException | None = None

    async def add(self, text: str) -> None:
        if not text:
            return
        async with self._lock:
            self._raise_failure()
            self._fragments.append(text)
            self._characters += len(text)
            if self._timer is None:
                self._timer = asyncio.create_task(self._flush_after_interval())
            if self._characters >= self.max_chars:
                await self._flush_locked(reason="size")

    async def flush(self, *, reason: str = "boundary") -> None:
        async with self._lock:
            self._raise_failure()
            await self._flush_locked(reason=reason)

    async def close(self) -> None:
        await self.flush(reason="exit")
        timer = self._timer
        self._timer = None
        if timer is not None and timer is not asyncio.current_task():
            timer.cancel()
            with suppress(asyncio.CancelledError):
                await timer

    async def _flush_after_interval(self) -> None:
        try:
            await asyncio.sleep(self.interval_seconds)
            async with self._lock:
                await self._flush_locked(reason="time")
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            self._failure = exc
        finally:
            if self._timer is asyncio.current_task():
                self._timer = None

    async def _flush_locked(self, *, reason: str) -> None:
        if not self._fragments:
            return
        fragments = list(self._fragments)
        timer = self._timer
        self._timer = None
        if timer is not None and timer is not asyncio.current_task():
            timer.cancel()
        text = "".join(fragments)
        await self.publish("token", {"run_id": self.run_id, "text": text})
        self._fragments = []
        self._characters = 0
        record_metric(
            "chat.redis.token_batch",
            context=RunContext(run_id=self.run_id, agent_name="chat_run_redis"),
            sink=get_observation_sink(),
            status="success",
            fields={
                "batch_reason": reason,
                "fragment_count": len(fragments),
                "payload_size_chars": len(text),
                "batched": len(fragments) > 1,
            },
        )

    def _raise_failure(self) -> None:
        if self._failure is not None:
            raise self._failure


class ChatRunManager:
    def __init__(self, agent_runtime: AgentRuntime, event_store: ChatRunRedis) -> None:
        self.agent_runtime = agent_runtime
        self.event_store = event_store
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._explicit_cancellations: set[str] = set()
        self._stopping = False

    async def start(self) -> None:
        async with AsyncSessionLocal() as db:
            stale_runs = await chat_run_service.list_stale_chat_runs(db)
        for run in stale_runs:
            output_text = run.output_text or ""
            last_sequence = run.last_event_sequence or 0
            try:
                snapshot = await self.event_store.get_snapshot(run.run_id)
                if snapshot is not None:
                    output_text = snapshot.output_text
                    last_sequence = snapshot.last_sequence
                last_sequence = await self.event_store.append(
                    run.run_id,
                    "error",
                    {"run_id": run.run_id, "message": chat_run_service.STALE_RUN_ERROR_MESSAGE},
                )
            except ChatRunEventStoreError:
                pass
            async with AsyncSessionLocal() as db:
                finalized = await chat_run_service.finalize_chat_run(
                    db,
                    run_id=run.run_id,
                    status=chat_run_service.RUN_STATUS_FAILED,
                    output_text=output_text,
                    last_sequence=last_sequence,
                    error_message=chat_run_service.STALE_RUN_ERROR_MESSAGE,
                )
            if finalized is not None:
                with suppress(ChatRunEventStoreError):
                    await self.event_store.append_done(
                        run.run_id,
                        sequence=finalized.last_event_sequence,
                        status=finalized.status,
                    )
        if stale_runs:
            log_observation(
                "chat.run.reconciled",
                context=RunContext(run_id="startup", agent_name="chat_run_manager"),
                sink=get_observation_sink(),
                status="failed",
                fields={"stale_run_count": len(stale_runs), "reason": "process_restart"},
            )

    def schedule(self, run_id: str) -> None:
        if self._stopping:
            raise RuntimeError("Chat run manager is stopping.")
        existing = self._tasks.get(run_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(self._execute_run(run_id), name=f"chat-run-{run_id}")
        self._tasks[run_id] = task
        task.add_done_callback(lambda completed, current_run_id=run_id: self._discard_task(current_run_id, completed))

    def _discard_task(self, run_id: str, task: asyncio.Task[None]) -> None:
        if self._tasks.get(run_id) is task:
            self._tasks.pop(run_id, None)
        self._explicit_cancellations.discard(run_id)

    async def stop(self) -> None:
        self._stopping = True
        tasks = list(self._tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._explicit_cancellations.clear()

    async def cancel(self, run_id: str) -> None:
        task = self._tasks.get(run_id)
        if task is None or task.done():
            async with AsyncSessionLocal() as db:
                run = await chat_run_service.get_chat_run(db, run_id)
            if run is not None and run.status in chat_run_service.ACTIVE_RUN_STATUSES:
                await self.agent_runtime.cancel_model_workflow(run.thread_id)
                await self._finalize_run(
                    run_id,
                    status=chat_run_service.RUN_STATUS_CANCELLED,
                    fallback_output=run.output_text or "",
                    fallback_sequence=run.last_event_sequence or 0,
                )
            return

        self._explicit_cancellations.add(run_id)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _execute_run(self, run_id: str) -> None:
        context: RunContext | None = None
        sink = get_observation_sink()
        run_observation_started = False
        local_output = ""
        publisher = _RunPublisher(self.event_store, run_id)
        token_buffer = _TokenEventBuffer(
            run_id,
            publisher.publish,
            interval_ms=get_redis_token_batch_interval_ms(),
            max_chars=get_redis_token_batch_max_chars(),
        )
        try:
            async with AsyncSessionLocal() as db:
                run = await chat_run_service.mark_chat_run_running(db, run_id)
                if run is None or run.status != chat_run_service.RUN_STATUS_RUNNING:
                    return
                attachments = None
                if run.attachment_ids:
                    attachments = await file_service.get_chat_attachments_by_ids(
                        db,
                        plan_id=run.plan_id,
                        thread_id=run.thread_id,
                        attachment_ids=list(run.attachment_ids),
                        user_id=run.user_id,
                    )
                context = RunContext(
                    run_id=run.run_id,
                    thread_id=run.thread_id,
                    plan_id=run.plan_id,
                    user_id=str(run.user_id),
                    agent_name="chat_run",
                )
                message = run.message
                thread_id = run.thread_id
                plan_id = run.plan_id
                user_id = run.user_id
                approval = dict(run.approval) if run.approval else None
                model_envelope = await chat_run_service.adopt_model_snapshot(
                    db,
                    run,
                    await self.agent_runtime.get_memory_reflection_checkpoint_values(thread_id)
                    if run.model_config_snapshot is None
                    else None,
                )

            log_observation(
                "chat.run.started",
                context=context,
                sink=sink,
                status="running",
                fields={"attachment_count": len(run.attachment_ids or []), "has_approval": bool(approval)},
            )
            run_observation_started = True
            await publisher.publish("metadata", {"thread_id": thread_id, "run_id": run_id})

            saw_approval = False
            saw_error = False
            async for event in self.agent_runtime.stream_agent_events(
                message,
                thread_id,
                run_id=run_id,
                user_id=str(user_id),
                plan_id=plan_id,
                attachments=attachments,
                approval=approval,
                model_envelope=model_envelope,
                run_context=context,
                observation_sink=sink,
            ):
                event_type = event.get("event")
                payload = event.get("data")
                if event_type not in chat_run_service.SUPPORTED_RUN_EVENTS or event_type == "done":
                    continue
                if not isinstance(payload, dict):
                    continue
                if event_type == "token" and isinstance(payload.get("text"), str):
                    local_output += payload["text"]
                    await token_buffer.add(payload["text"])
                else:
                    await token_buffer.flush(reason="event_boundary")
                    await publisher.publish(event_type, payload)
                saw_approval = saw_approval or event_type == "approval"
                saw_error = saw_error or event_type == "error"

            await token_buffer.close()
            final_status = (
                chat_run_service.RUN_STATUS_WAITING_APPROVAL
                if saw_approval
                else chat_run_service.RUN_STATUS_FAILED
                if saw_error
                else chat_run_service.RUN_STATUS_SUCCEEDED
            )
            await self._finalize_run(
                run_id,
                status=final_status,
                fallback_output=local_output,
                fallback_sequence=publisher.last_sequence,
            )
            log_observation(
                "chat.run.completed" if final_status != chat_run_service.RUN_STATUS_FAILED else "chat.run.failed",
                context=context,
                sink=sink,
                status="success" if final_status != chat_run_service.RUN_STATUS_FAILED else "failed",
                fields={"run_status": final_status},
            )
        except asyncio.CancelledError:
            with suppress(ChatRunEventStoreError):
                await token_buffer.close()
            if run_id in self._explicit_cancellations:
                if context is not None and context.thread_id:
                    await self.agent_runtime.cancel_model_workflow(context.thread_id)
                await self._finalize_run(
                    run_id,
                    status=chat_run_service.RUN_STATUS_CANCELLED,
                    fallback_output=local_output,
                    fallback_sequence=publisher.last_sequence,
                )
                if context is not None and run_observation_started:
                    log_observation("chat.run.cancelled", context=context, sink=sink, status="success")
                return
            raise
        except Exception as exc:
            with suppress(Exception):
                await token_buffer.close()
            if context is None:
                async with AsyncSessionLocal() as db:
                    failed_run = await chat_run_service.get_chat_run(db, run_id)
                if failed_run is not None:
                    context = RunContext(
                        run_id=run_id,
                        thread_id=failed_run.thread_id,
                        plan_id=failed_run.plan_id,
                        user_id=str(failed_run.user_id),
                        agent_name="chat_run",
                    )
            context = context or RunContext(run_id=run_id, agent_name="chat_run")
            log_observation(
                "chat.run.failed" if run_observation_started else "chat.run.start_failed",
                context=context,
                sink=sink,
                status="failed",
                fields={
                    "error_category": categorize_error(exc),
                    "error_type": exc.__class__.__name__,
                    "error_message": "Chat run execution failed.",
                },
            )
            user_message = "对话处理失败，请稍后重试。"
            with suppress(ChatRunEventStoreError):
                await publisher.publish("error", {"run_id": run_id, "message": user_message})
            await self._finalize_run(
                run_id,
                status=chat_run_service.RUN_STATUS_FAILED,
                fallback_output=local_output,
                fallback_sequence=publisher.last_sequence,
                error_message=user_message,
                prefer_fallback_output=True,
            )

    async def _finalize_run(
        self,
        run_id: str,
        *,
        status: str,
        fallback_output: str,
        fallback_sequence: int,
        error_message: str | None = None,
        prefer_fallback_output: bool = False,
    ) -> Any:
        output_text = fallback_output
        last_sequence = fallback_sequence
        try:
            snapshot = await self.event_store.get_snapshot(run_id)
            if snapshot is not None:
                if not prefer_fallback_output:
                    output_text = snapshot.output_text
                last_sequence = max(last_sequence, snapshot.last_sequence)
        except ChatRunEventStoreError:
            pass
        reflection_candidates = None
        if hasattr(self.agent_runtime, "get_memory_reflection_checkpoint_values"):
            async with AsyncSessionLocal() as db:
                source_run = await chat_run_service.get_chat_run(db, run_id)
            if source_run is not None:
                checkpoint_values = None
                try:
                    checkpoint_values = await self.agent_runtime.get_memory_reflection_checkpoint_values(
                        source_run.thread_id
                    )
                except Exception as exc:
                    log_observation(
                        "memory.reflection.snapshot_unavailable",
                        context=RunContext(
                            run_id=source_run.run_id,
                            thread_id=source_run.thread_id,
                            plan_id=source_run.plan_id,
                            user_id=str(source_run.user_id),
                            agent_name="chat_run_manager",
                        ),
                        sink=get_observation_sink(),
                        status="failed",
                        fields={"error_category": categorize_error(exc), "error_type": exc.__class__.__name__},
                    )
                try:
                    reflection_candidates = build_reflection_job_candidates(
                        run=source_run,
                        status=status,
                        checkpoint_values=checkpoint_values,
                    )
                except Exception as exc:
                    reflection_candidates = []
                    log_observation(
                        "memory.reflection.snapshot_build_failed",
                        context=RunContext(
                            run_id=source_run.run_id,
                            thread_id=source_run.thread_id,
                            plan_id=source_run.plan_id,
                            user_id=str(source_run.user_id),
                            agent_name="chat_run_manager",
                        ),
                        sink=get_observation_sink(),
                        status="failed",
                        fields={"error_category": categorize_error(exc), "error_type": exc.__class__.__name__},
                    )
        async with AsyncSessionLocal() as db:
            finalize_kwargs = {
                "run_id": run_id,
                "status": status,
                "output_text": output_text,
                "last_sequence": last_sequence,
                "error_message": error_message,
            }
            if reflection_candidates is not None:
                finalize_kwargs["reflection_candidates"] = reflection_candidates
            run = await chat_run_service.finalize_chat_run(db, **finalize_kwargs)
        if run is None:
            return None
        try:
            await self.event_store.append_done(
                run_id,
                sequence=run.last_event_sequence,
                status=run.status,
            )
        except ChatRunEventStoreError:
            log_observation(
                "chat.redis.terminal_recovery_required",
                context=RunContext(run_id=run_id, agent_name="chat_run_manager"),
                sink=get_observation_sink(),
                status="failed",
                fields={"operation": "terminal", "error_category": "redis_error"},
            )
        return run


def get_chat_run_manager(request: Request) -> ChatRunManager:
    manager = getattr(request.app.state, "chat_run_manager", None)
    if manager is None:
        raise RuntimeError("Chat run manager is not initialized.")
    return manager

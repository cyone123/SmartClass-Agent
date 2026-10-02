from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from datetime import UTC, datetime

from langgraph.store.base import BaseStore

from app.config import get_memory_reflection_poll_seconds, get_memory_reflection_shadow_mode
from app.core.memory import extract_experience_memory_proposal, extract_profile_memory_proposal
from app.core.model_access import current_snapshot, use_snapshot
from app.core.model_access.factory import factory
from app.core.observability import (
    RunContext,
    categorize_error,
    get_observation_sink,
    log_observation,
    record_metric,
    trace_span,
)
from app.dependencies.db import AsyncSessionLocal
from app.models.memory_reflection import MemoryReflectionJob
from app.schemas.memory_reflection import ExperienceReflectionSnapshot, ProfileReflectionSnapshot
from app.services.memory_reflection_service import MemoryReflectionJobRepository
from app.services.memory_service import MemoryService


class MemoryReflectionWorker:
    def __init__(self, memory_store: BaseStore, *, shadow: bool | None = None) -> None:
        self.memory_store = memory_store
        self.shadow = get_memory_reflection_shadow_mode() if shadow is None else shadow
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._next_cleanup_at = 0.0

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        async with AsyncSessionLocal() as db:
            interrupted_kinds = await MemoryReflectionJobRepository(db).fail_interrupted()
        for job_kind in interrupted_kinds:
            context = RunContext(run_id="startup", agent_name="memory_worker")
            log_observation(
                "memory.reflection.interrupted",
                context=context,
                sink=get_observation_sink(),
                status="failed",
                fields={
                    "job_kind": job_kind,
                    "job_state": "failed",
                    "error_category": "worker_interrupted",
                },
            )
            record_metric(
                "memory.reflection.job",
                context=context,
                sink=get_observation_sink(),
                status="failed",
                fields={
                    "job_kind": job_kind,
                    "job_state": "failed",
                    "error_category": "worker_interrupted",
                },
            )
        self._task = asyncio.create_task(self._run(), name="memory-reflection-worker")

    async def stop(self, *, timeout_seconds: float = 5.0) -> None:
        self._stop_event.set()
        task = self._task
        self._task = None
        if task is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
        except TimeoutError:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                processed = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                processed = 0
                log_observation(
                    "memory.worker.poll_failed",
                    context=RunContext(run_id="worker", agent_name="memory_worker"),
                    sink=get_observation_sink(),
                    status="failed",
                    fields={"error_category": categorize_error(exc), "error_type": exc.__class__.__name__},
                )
            if processed:
                continue
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=get_memory_reflection_poll_seconds())
            except TimeoutError:
                pass

    async def run_once(self) -> int:
        async with AsyncSessionLocal() as db:
            repository = MemoryReflectionJobRepository(db)
            queue_depth = await repository.queue_depth()
            if time.monotonic() >= self._next_cleanup_at:
                await repository.cleanup_terminal()
                self._next_cleanup_at = time.monotonic() + 3600
            job = await repository.take_next()
        record_metric(
            "memory.reflection.queue",
            context=RunContext(run_id="worker", agent_name="memory_worker"),
            sink=get_observation_sink(),
            status="success",
            fields={"queue_depth": queue_depth},
        )
        if job is not None:
            await self._process(job)
            return 1
        return 0

    async def _process(self, job) -> None:
        context = RunContext(
            run_id=job.source_run_id,
            thread_id=job.source_thread_id,
            plan_id=job.source_plan_id,
            user_id=str(job.user_id),
            agent_name="memory_worker",
        )
        sink = get_observation_sink()
        with trace_span(
            "memory.reflection.process",
            context=context,
            sink=sink,
            fields={"job_kind": job.kind},
        ):
            await self._process_claimed(job, context=context, sink=sink)

    async def _process_claimed(self, job, *, context: RunContext, sink) -> None:
        started = time.monotonic()
        log_observation(
            "memory.reflection.taken",
            context=context,
            sink=sink,
            status="running",
            fields={"job_kind": job.kind, "job_state": "running"},
        )
        record_metric(
            "memory.reflection.job",
            context=context,
            sink=sink,
            status="running",
            fields={"job_kind": job.kind, "job_state": "running"},
        )
        try:
            if job.snapshot_version not in {1, 2}:
                raise ValueError("Unsupported memory reflection snapshot version.")
            if not job.snapshot.get("model_config_snapshot"):
                adopted = {
                    **job.snapshot,
                    "schema_version": 2,
                    "legacy_snapshot_adopted": True,
                    "model_config_snapshot": current_snapshot().model_dump(mode="json"),
                }
                async with AsyncSessionLocal() as db:
                    stored = await db.get(MemoryReflectionJob, job.job_id, with_for_update=True)
                    if stored is None:
                        raise ValueError("Reflection job disappeared before model configuration adoption")
                    if not stored.snapshot.get("model_config_snapshot"):
                        stored.snapshot = adopted
                        stored.snapshot_version = 2
                        await db.commit()
                    job.snapshot = stored.snapshot
                    job.snapshot_version = stored.snapshot_version
                log_observation(
                    "model.config.adopted",
                    context=context,
                    sink=sink,
                    status="success",
                    fields={"legacy_snapshot_adopted": True},
                )
            with use_snapshot(job.snapshot["model_config_snapshot"]) as fixed:
                binding = fixed.roles["memory"]
                factory.secrets.resolve(fixed.connections[fixed.models[binding.model].connection].credential)
                if job.snapshot_version not in {1, 2}:
                    raise ValueError("Unsupported memory reflection snapshot version.")
                if job.kind == "profile":
                    snapshot = ProfileReflectionSnapshot.model_validate(job.snapshot)
                    proposal = await extract_profile_memory_proposal(
                        store=self.memory_store, snapshot=snapshot, run_context=context, observation_sink=sink
                    )
                elif job.kind == "experience":
                    snapshot = ExperienceReflectionSnapshot.model_validate(job.snapshot)
                    proposal = await extract_experience_memory_proposal(
                        store=self.memory_store, snapshot=snapshot, run_context=context, observation_sink=sink
                    )
                else:
                    raise ValueError("Unsupported memory reflection kind.")

            async with AsyncSessionLocal() as db:
                repository = MemoryReflectionJobRepository(db)
                if self.shadow:
                    await repository.skip(job.job_id, category="shadow_mode")
                    outcome = "skipped"
                elif proposal.operation == "noop":
                    await repository.skip(job.job_id, category="policy_skip")
                    outcome = "skipped"
                else:
                    result = await MemoryService(db, self.memory_store).apply_automatic(
                        user_id=job.user_id,
                        job_id=job.job_id,
                        proposal=proposal,
                        source_thread_id=job.source_thread_id,
                        source_plan_id=job.source_plan_id,
                        job_captured_at=snapshot.captured_at,
                    )
                    if result.status == "applied":
                        await repository.succeed(job.job_id, memory_id=result.memory_id, memory_version=result.version)
                        outcome = "succeeded"
                    else:
                        await repository.skip(job.job_id, category=result.status)
                        outcome = "skipped"
            log_observation(
                f"memory.reflection.{outcome}",
                context=context,
                sink=sink,
                status="success",
                fields={"job_kind": job.kind, "job_state": outcome},
            )
            record_metric(
                "memory.reflection.job",
                context=context,
                sink=sink,
                status="success",
                duration_ms=int((time.monotonic() - started) * 1000),
                fields={
                    "job_kind": job.kind,
                    "job_state": outcome,
                    "queue_latency_seconds": max(0.0, (datetime.now(UTC) - snapshot.captured_at).total_seconds()),
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            category = categorize_error(exc)
            async with AsyncSessionLocal() as db:
                await MemoryReflectionJobRepository(db).fail(
                    job.job_id,
                    category=category,
                )
            log_observation(
                "memory.reflection.failed",
                context=context,
                sink=sink,
                status="failed",
                fields={
                    "job_kind": job.kind,
                    "job_state": "failed",
                    "error_category": category,
                    "error_type": exc.__class__.__name__,
                },
            )
            record_metric(
                "memory.reflection.job",
                context=context,
                sink=sink,
                status="failed",
                fields={
                    "job_kind": job.kind,
                    "job_state": "failed",
                    "error_category": category,
                },
            )

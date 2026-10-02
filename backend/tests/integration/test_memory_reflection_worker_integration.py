from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.dependencies.db import AsyncSessionLocal, async_engine
from app.models.memory_reflection import MemoryMutationGuard, MemoryReflectionJob
from app.schemas.memory_reflection import MemoryMutationProposal, ProfileReflectionSnapshot
from app.services.memory_reflection_service import (
    MemoryReflectionJobRepository,
    ReflectionJobCandidate,
    register_reflection_candidates,
)
from app.services.memory_service import MemoryService, deterministic_memory_id
from tests.test_long_term_memory import FakeStore

pytestmark = pytest.mark.integration


async def _ensure_tables() -> None:
    async with async_engine.begin() as connection:
        await connection.run_sync(MemoryReflectionJob.__table__.create, checkfirst=True)
        await connection.run_sync(MemoryMutationGuard.__table__.create, checkfirst=True)
        await connection.exec_driver_sql("UPDATE memory_reflection_jobs SET status = 'pending' WHERE status = 'retry'")
        await connection.exec_driver_sql("DROP INDEX IF EXISTS ix_memory_reflection_jobs_claim")
        for column in ("attempts", "available_at", "lease_owner", "lease_expires_at"):
            await connection.exec_driver_sql(f"ALTER TABLE memory_reflection_jobs DROP COLUMN IF EXISTS {column}")
        await connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_memory_reflection_jobs_pending ON memory_reflection_jobs(status, created_at)"
        )


def _candidate(*, user_id: str, source_run_id: str) -> ReflectionJobCandidate:
    snapshot = ProfileReflectionSnapshot(
        user_id=user_id,
        source_run_id=source_run_id,
        source_thread_id=f"thread-{source_run_id}",
        business_stage="succeeded",
        captured_at=datetime.now(UTC),
        user_input="请记住我偏好案例教学",
    )
    return ReflectionJobCandidate(
        kind="profile",
        business_stage="succeeded",
        extractor_version="v1",
        snapshot=snapshot,
    )


def test_postgres_concurrent_registration_atomic_take_and_interrupted_failure() -> None:
    async def exercise() -> None:
        await _ensure_tables()
        token = uuid4().hex[:12]
        user_id = f"integration-{token}"
        source_run_id = f"run-{token}"
        candidate = _candidate(user_id=user_id, source_run_id=source_run_id)

        async def register():
            async with AsyncSessionLocal() as db:
                rows = await register_reflection_candidates(db, [candidate])
                await db.commit()
                return rows[0].job_id

        first_id, second_id = await asyncio.gather(register(), register())
        assert first_id == second_id
        async with AsyncSessionLocal() as db:
            rows = list(
                (
                    await db.execute(
                        select(MemoryReflectionJob).where(MemoryReflectionJob.source_run_id == source_run_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1

        async def take():
            async with AsyncSessionLocal() as db:
                return await MemoryReflectionJobRepository(db).take_next()

        taken = await asyncio.gather(take(), take())
        assert sum(row is not None for row in taken) == 1
        assert next(row for row in taken if row is not None).job_id == first_id

        async with AsyncSessionLocal() as db:
            row = await db.get(MemoryReflectionJob, first_id)
            assert row.status == "running"
            assert await MemoryReflectionJobRepository(db).fail_interrupted() == ["profile"]
            await db.refresh(row)
            assert row.status == "failed"
            assert row.error_category == "worker_interrupted"
        assert await take() is None

        async with AsyncSessionLocal() as db:
            await db.execute(delete(MemoryReflectionJob).where(MemoryReflectionJob.user_id == user_id))
            await db.commit()
        await async_engine.dispose()

    asyncio.run(exercise())


def test_postgres_advisory_lock_stale_guards_and_reconciliation() -> None:
    async def exercise() -> None:
        await _ensure_tables()
        token = uuid4().hex[:12]
        user_id = f"integration-{token}"
        store = FakeStore()
        async with AsyncSessionLocal() as db:
            created = await MemoryService(db, store).create_manual(
                user_id=user_id,
                kind="profile",
                value={"title": "风格", "summary": "旧", "content": "旧"},
            )
        memory_id = created["id"]
        captured_at = datetime.now(UTC)
        async with AsyncSessionLocal() as db:
            await MemoryService(db, store).update_manual(
                user_id=user_id,
                kind="profile",
                memory_id=memory_id,
                value={"summary": "手工更新", "content": "手工更新"},
            )
        stale = MemoryMutationProposal(
            operation="update",
            kind="profile",
            target_memory_id=memory_id,
            base_version=1,
            title="风格",
            content="后台旧值",
        )
        async with AsyncSessionLocal() as db:
            result = await MemoryService(db, store).apply_automatic(
                user_id=user_id,
                job_id=f"job-{token}",
                proposal=stale,
                source_thread_id="thread",
                source_plan_id=None,
                job_captured_at=captured_at,
            )
        assert result.status == "stale"
        delete_captured_at = datetime.now(UTC)
        async with AsyncSessionLocal() as db:
            await MemoryService(db, store).delete_manual(
                user_id=user_id,
                kind="profile",
                memory_id=memory_id,
            )
        async with AsyncSessionLocal() as db:
            deleted_result = await MemoryService(db, store).apply_automatic(
                user_id=user_id,
                job_id=f"deleted-{token}",
                proposal=stale,
                source_thread_id="thread",
                source_plan_id=None,
                job_captured_at=delete_captured_at,
            )
        assert deleted_result.status == "stale"
        assert memory_id not in store.data.get(("users", user_id, "profile"), {})

        create = MemoryMutationProposal(operation="create", kind="experience", title="经验", content="可复用策略")
        job_id = f"gap-{token}"
        automatic_id = deterministic_memory_id(job_id)
        namespace = ("users", user_id, "experiences")
        await store.aput(
            namespace,
            automatic_id,
            {
                "kind": "experience",
                "title": "经验",
                "content": "可复用策略",
                "_guard_version": 1,
                "_last_applied_job_id": job_id,
            },
        )
        async with AsyncSessionLocal() as db:
            repaired = await MemoryService(db, store).apply_automatic(
                user_id=user_id,
                job_id=job_id,
                proposal=create,
                source_thread_id="thread",
                source_plan_id=None,
                job_captured_at=datetime.now(UTC),
            )
        assert repaired.status == "applied"
        assert list(store.data[namespace]) == [automatic_id]
        async with AsyncSessionLocal() as db:
            replayed = await MemoryService(db, store).apply_automatic(
                user_id=user_id,
                job_id=job_id,
                proposal=create,
                source_thread_id="thread",
                source_plan_id=None,
                job_captured_at=datetime.now(UTC),
            )
        assert replayed.status == "applied"
        assert list(store.data[namespace]) == [automatic_id]

        async with AsyncSessionLocal() as db:
            await db.execute(delete(MemoryMutationGuard).where(MemoryMutationGuard.user_id == user_id))
            await db.commit()
        await async_engine.dispose()

    asyncio.run(exercise())


def test_postgres_advisory_lock_serializes_one_user_not_different_users() -> None:
    class BlockingStore(FakeStore):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0
            self.first_entered = asyncio.Event()
            self.second_entered = asyncio.Event()
            self.release = asyncio.Event()

        async def aput(self, namespace, key, value, index=None, *, ttl=None):
            self.calls += 1
            if self.calls == 1:
                self.first_entered.set()
                await self.release.wait()
            else:
                self.second_entered.set()
            await super().aput(namespace, key, value, index=index, ttl=ttl)

    async def create(store, user_id):
        async with AsyncSessionLocal() as db:
            return await MemoryService(db, store).create_manual(
                user_id=user_id,
                kind="profile",
                value={"title": "风格", "summary": "偏好", "content": "偏好"},
            )

    async def exercise() -> None:
        await _ensure_tables()
        token = uuid4().hex[:12]
        same_user = f"integration-same-{token}"
        store = BlockingStore()
        first = asyncio.create_task(create(store, same_user))
        await store.first_entered.wait()
        second = asyncio.create_task(create(store, same_user))
        await asyncio.sleep(0.05)
        assert not store.second_entered.is_set()
        store.release.set()
        await asyncio.gather(first, second)
        assert store.second_entered.is_set()

        different_store = BlockingStore()
        user_a = f"integration-a-{token}"
        user_b = f"integration-b-{token}"
        first = asyncio.create_task(create(different_store, user_a))
        await different_store.first_entered.wait()
        second = asyncio.create_task(create(different_store, user_b))
        await asyncio.wait_for(different_store.second_entered.wait(), timeout=1)
        different_store.release.set()
        await asyncio.gather(first, second)

        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(MemoryMutationGuard).where(MemoryMutationGuard.user_id.in_((same_user, user_a, user_b)))
            )
            await db.commit()
        await async_engine.dispose()

    asyncio.run(exercise())

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langgraph.store.base import BaseStore
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.memory import (
    delete_memory_item,
    experience_namespace,
    get_memory_item,
    profile_namespace,
    put_memory_item,
    search_memory_items,
)
from app.models.memory_reflection import MemoryMutationGuard
from app.schemas.memory_reflection import MemoryMutationProposal


@dataclass(frozen=True)
class MemoryMutationResult:
    status: str
    memory_id: str | None = None
    version: int | None = None
    memory: dict[str, Any] | None = None


def _namespace(user_id: str, kind: str) -> tuple[str, ...]:
    return profile_namespace(str(user_id)) if kind == "profile" else experience_namespace(str(user_id))


def _advisory_key(user_id: str) -> int:
    raw = hashlib.sha256(f"smartclass-memory:{user_id}".encode()).digest()[:8]
    return int.from_bytes(raw, byteorder="big", signed=True)


def deterministic_memory_id(job_id: str) -> str:
    return hashlib.sha256(f"memory-reflection:{job_id}".encode()).hexdigest()[:32]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class MemoryService:
    def __init__(self, db: AsyncSession, store: BaseStore) -> None:
        self.db = db
        self.store = store

    async def _lock_user(self, user_id: str) -> None:
        bind = self.db.get_bind()
        if bind.dialect.name == "postgresql":
            await self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _advisory_key(user_id)})

    async def _guard(self, *, user_id: str, kind: str, memory_id: str) -> MemoryMutationGuard:
        stmt = (
            select(MemoryMutationGuard)
            .where(
                MemoryMutationGuard.user_id == user_id,
                MemoryMutationGuard.kind == kind,
                MemoryMutationGuard.memory_id == memory_id,
            )
            .with_for_update()
        )
        guard = (await self.db.execute(stmt)).scalar_one_or_none()
        if guard is not None:
            return guard
        existing = await get_memory_item(self.store, _namespace(user_id, kind), memory_id)
        guard = MemoryMutationGuard(
            guard_id=uuid4().hex,
            user_id=user_id,
            kind=kind,
            memory_id=memory_id,
            version=max(int((existing or {}).get("_guard_version") or 0), 0),
            last_applied_job_id=(existing or {}).get("_last_applied_job_id"),
        )
        self.db.add(guard)
        await self.db.flush()
        return guard

    async def create_manual(self, *, user_id: str, kind: str, value: dict[str, Any]) -> dict[str, Any]:
        await self._lock_user(user_id)
        memory_id = uuid4().hex
        guard = await self._guard(user_id=user_id, kind=kind, memory_id=memory_id)
        guard.version += 1
        guard.deleted_at = None
        guard.last_manual_mutation_at = datetime.now(UTC)
        payload = {**value, "_guard_version": guard.version, "_last_applied_job_id": None}
        result = await put_memory_item(self.store, _namespace(user_id, kind), value=payload, key=memory_id)
        await self.db.commit()
        return result

    async def update_manual(self, *, user_id: str, kind: str, memory_id: str, value: dict[str, Any]) -> dict[str, Any]:
        await self._lock_user(user_id)
        guard = await self._guard(user_id=user_id, kind=kind, memory_id=memory_id)
        guard.version += 1
        guard.deleted_at = None
        guard.last_manual_mutation_at = datetime.now(UTC)
        guard.last_applied_job_id = None
        payload = {**value, "_guard_version": guard.version, "_last_applied_job_id": None}
        result = await put_memory_item(self.store, _namespace(user_id, kind), value=payload, key=memory_id)
        await self.db.commit()
        return result

    async def delete_manual(self, *, user_id: str, kind: str, memory_id: str) -> None:
        await self._lock_user(user_id)
        guard = await self._guard(user_id=user_id, kind=kind, memory_id=memory_id)
        guard.version += 1
        guard.deletion_generation += 1
        guard.deleted_at = datetime.now(UTC)
        guard.last_manual_mutation_at = guard.deleted_at
        guard.last_applied_job_id = None
        await delete_memory_item(self.store, _namespace(user_id, kind), memory_id)
        await self.db.commit()

    async def apply_automatic(
        self,
        *,
        user_id: str,
        job_id: str,
        proposal: MemoryMutationProposal,
        source_thread_id: str | None,
        source_plan_id: int | None,
        job_captured_at: datetime,
    ) -> MemoryMutationResult:
        if proposal.operation == "noop":
            return MemoryMutationResult(status="skipped")
        memory_id = (
            deterministic_memory_id(job_id) if proposal.operation == "create" else str(proposal.target_memory_id or "")
        )
        if not memory_id:
            return MemoryMutationResult(status="skipped")
        await self._lock_user(user_id)
        guard = await self._guard(user_id=user_id, kind=proposal.kind, memory_id=memory_id)
        existing = await get_memory_item(self.store, _namespace(user_id, proposal.kind), memory_id)

        if guard.last_applied_job_id == job_id:
            await self.db.commit()
            return MemoryMutationResult("applied", memory_id, guard.version, existing)
        if existing and existing.get("_last_applied_job_id") == job_id:
            guard.version = max(guard.version, int(existing.get("_guard_version") or 0))
            guard.last_applied_job_id = job_id
            guard.deleted_at = None
            await self.db.commit()
            return MemoryMutationResult("applied", memory_id, guard.version, existing)
        if proposal.operation == "create":
            current_items = await search_memory_items(self.store, _namespace(user_id, proposal.kind), limit=100)
            duplicate = next(
                (
                    item
                    for item in current_items
                    if str(item.get("id") or "") != memory_id
                    and str(item.get("title") or "").strip().casefold() == proposal.title.strip().casefold()
                    and str(item.get("content") or "").strip() == proposal.content.strip()
                ),
                None,
            )
            if duplicate is not None:
                await self.db.rollback()
                return MemoryMutationResult(status="stale", memory_id=str(duplicate.get("id") or "") or None)
        if guard.last_manual_mutation_at is not None and _as_utc(guard.last_manual_mutation_at) > _as_utc(
            job_captured_at
        ):
            current_version = guard.version
            await self.db.rollback()
            return MemoryMutationResult(status="stale", memory_id=memory_id, version=current_version)
        if guard.deleted_at is not None:
            current_version = guard.version
            await self.db.rollback()
            return MemoryMutationResult(status="stale", memory_id=memory_id, version=current_version)
        if proposal.operation == "update" and proposal.base_version != guard.version:
            current_version = guard.version
            await self.db.rollback()
            return MemoryMutationResult(status="stale", memory_id=memory_id, version=current_version)

        next_version = guard.version + 1
        payload = {
            "kind": proposal.kind,
            "title": proposal.title or "Memory",
            "summary": proposal.summary or proposal.content[:240],
            "content": proposal.content,
            "tags": proposal.tags,
            "source_thread_id": source_thread_id,
            "source_plan_id": source_plan_id,
            "_guard_version": next_version,
            "_last_applied_job_id": job_id,
        }
        result = await put_memory_item(self.store, _namespace(user_id, proposal.kind), value=payload, key=memory_id)
        guard.version = next_version
        guard.last_applied_job_id = job_id
        guard.deleted_at = None
        await self.db.commit()
        return MemoryMutationResult("applied", memory_id, next_version, result)

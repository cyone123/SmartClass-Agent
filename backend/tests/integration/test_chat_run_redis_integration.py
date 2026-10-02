from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import asyncpg
import pytest
from redis.asyncio import Redis

from app.config import get_db_uri, get_redis_url
from app.core.chat_run_events import ChatRunEventStoreUnavailable, ChatRunRedis
from app.core.chat_runs import ChatRunManager
from app.dependencies.db import AsyncSessionLocal, async_engine
from app.migrations.v20260907_drop_agent_run_events import upgrade
from app.models import Base
from app.services import chat_run_service

pytestmark = pytest.mark.integration


async def _connected_store(*, retention_seconds: int = 60) -> ChatRunRedis:
    url = get_redis_url()
    command = Redis.from_url(url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
    reader = Redis.from_url(url, decode_responses=True, socket_connect_timeout=1, socket_timeout=2)
    store = ChatRunRedis(
        command,
        reader,
        environment="integration",
        key_prefix="sc-test",
        active_ttl_seconds=60,
        terminal_retention_seconds=retention_seconds,
        operation_timeout_seconds=1,
        read_block_ms=100,
        read_batch_size=100,
    )
    try:
        await store.start()
    except Exception as exc:
        await store.close()
        pytest.skip(f"Redis integration service is unavailable: {exc.__class__.__name__}")
    return store


def test_real_redis_append_replay_snapshot_terminal_and_retention() -> None:
    async def exercise() -> None:
        store = await _connected_store(retention_seconds=1)
        run_id = uuid4().hex
        try:
            sequences = await asyncio.gather(
                *(store.append(run_id, "token", {"text": fragment}) for fragment in ("a", "b", "c"))
            )
            assert sorted(sequences) == [1, 2, 3]
            replay_a, replay_b = await asyncio.gather(
                store.read_after(run_id, 0, block_ms=0),
                store.read_after(run_id, 0, block_ms=0),
            )
            assert replay_a == replay_b
            snapshot = await store.get_snapshot(run_id)
            assert snapshot is not None
            assert snapshot.output_text == "".join(event.payload["text"] for event in replay_a)
            await store.command_client.script_flush()
            assert await store.append(run_id, "progress", {"step": "after-script-cache-loss"}) == 4
            await store.command_client.script_flush()
            assert await store.append_done(run_id, sequence=5, status="succeeded") is True
            assert await store.append_done(run_id, sequence=5, status="succeeded") is False
            await asyncio.sleep(1.1)
            assert await store.get_snapshot(run_id) is None
            assert await store.read_after(run_id, 0, block_ms=0) == []
        finally:
            await store.cleanup(run_id)
            await store.close()

    asyncio.run(exercise())


def test_unavailable_real_redis_is_explicit() -> None:
    async def exercise() -> None:
        command = Redis.from_url(
            "redis://127.0.0.1:1/0",
            decode_responses=True,
            socket_connect_timeout=0.05,
            socket_timeout=0.05,
        )
        store = ChatRunRedis(command, command, environment="integration", operation_timeout_seconds=0.05)
        try:
            with pytest.raises(ChatRunEventStoreUnavailable):
                await store.ensure_ready()
        finally:
            await store.close()

    asyncio.run(exercise())


def test_real_postgres_redis_active_terminal_and_stale_reconciliation() -> None:
    async def exercise() -> None:
        store = await _connected_store(retention_seconds=60)
        unique = uuid4().hex
        active_run_id = uuid4().hex
        stale_run_id = uuid4().hex
        thread_id = uuid4().hex
        stale_thread_id = uuid4().hex
        connection = None
        user_id = None
        plan_id = None
        session_ids: list[int] = []
        try:
            async with async_engine.begin() as engine_connection:
                await engine_connection.run_sync(Base.metadata.create_all)
            connection = await asyncpg.connect(get_db_uri(), timeout=2)
            user_id = await connection.fetchval(
                """
                INSERT INTO users (username, password_hash, display_name, role, is_active, is_superuser)
                VALUES ($1, 'integration-only', 'Redis integration', 'teacher', true, false)
                RETURNING id
                """,
                f"redis-integration-{unique}",
            )
            plan_id = await connection.fetchval(
                "INSERT INTO teaching_plans (user_id, name) VALUES ($1, 'Redis integration') RETURNING id",
                user_id,
            )
            for current_thread in (thread_id, stale_thread_id):
                session_ids.append(
                    await connection.fetchval(
                        """
                        INSERT INTO teaching_sessions (name, thread_id, user_id, plan_id)
                        VALUES ('Redis integration', $1, $2, $3)
                        RETURNING id
                        """,
                        current_thread,
                        user_id,
                        plan_id,
                    )
                )
            await connection.execute(
                """
                INSERT INTO agent_runs
                    (run_id, thread_id, user_id, plan_id, status, message, attachment_ids,
                     output_text, last_event_sequence)
                VALUES ($1, $2, $3, $4, 'running', 'integration', '[]'::json, '', 0)
                """,
                active_run_id,
                thread_id,
                user_id,
                plan_id,
            )
            await store.append(active_run_id, "token", {"text": "live"})
            live_snapshot = await store.get_snapshot(active_run_id)
            async with AsyncSessionLocal() as db:
                active_run = await chat_run_service.get_chat_run(db, active_run_id)
                active_payload = chat_run_service.serialize_chat_run(active_run, live_snapshot=live_snapshot)
                assert active_payload["output_text"] == "live"
                assert active_payload["last_event_sequence"] == 1
                terminal_run = await chat_run_service.finalize_chat_run(
                    db,
                    run_id=active_run_id,
                    status=chat_run_service.RUN_STATUS_SUCCEEDED,
                    output_text=live_snapshot.output_text,
                    last_sequence=live_snapshot.last_sequence,
                )
            assert terminal_run is not None
            assert terminal_run.last_event_sequence == 2
            assert await store.append_done(active_run_id, sequence=2, status=terminal_run.status) is True
            terminal_payload = chat_run_service.serialize_chat_run(
                terminal_run,
                live_snapshot=SimpleNamespace(output_text="must-not-overlay", last_sequence=99),
            )
            assert terminal_payload["output_text"] == "live"
            assert terminal_payload["last_event_sequence"] == 2

            await connection.execute(
                """
                INSERT INTO agent_runs
                    (run_id, thread_id, user_id, plan_id, status, message, attachment_ids,
                     output_text, last_event_sequence)
                VALUES ($1, $2, $3, $4, 'running', 'integration', '[]'::json, '', 0)
                """,
                stale_run_id,
                stale_thread_id,
                user_id,
                plan_id,
            )
            await store.append(stale_run_id, "token", {"text": "partial"})
            manager = ChatRunManager(SimpleNamespace(), store)
            await manager.start()
            async with AsyncSessionLocal() as db:
                stale_run = await chat_run_service.get_chat_run(db, stale_run_id)
            assert stale_run is not None
            assert stale_run.status == chat_run_service.RUN_STATUS_FAILED
            assert stale_run.output_text == "partial"
            stale_events = await store.read_after(stale_run_id, 0, block_ms=0)
            assert [event.event_type for event in stale_events] == ["token", "error", "done"]
        finally:
            await store.cleanup(active_run_id)
            await store.cleanup(stale_run_id)
            await store.close()
            if connection is not None:
                await connection.execute(
                    "DELETE FROM agent_runs WHERE run_id = ANY($1::text[])", [active_run_id, stale_run_id]
                )
                if session_ids:
                    await connection.execute("DELETE FROM teaching_sessions WHERE id = ANY($1::integer[])", session_ids)
                if plan_id is not None:
                    await connection.execute("DELETE FROM teaching_plans WHERE id = $1", plan_id)
                if user_id is not None:
                    await connection.execute("DELETE FROM users WHERE id = $1", user_id)
                await connection.close()

    asyncio.run(exercise())


def test_real_postgres_schema_upgrade_empty_missing_and_populated_states() -> None:
    async def exercise() -> None:
        try:
            connection = await asyncpg.connect(get_db_uri(), timeout=2)
        except Exception as exc:
            pytest.skip(f"PostgreSQL integration service is unavailable: {exc.__class__.__name__}")
        transaction = connection.transaction()
        await transaction.start()
        try:
            existing_table = await connection.fetchval("SELECT to_regclass('public.agent_run_events')")
            existing_count = (
                await connection.fetchval("SELECT count(*) FROM public.agent_run_events") if existing_table else 0
            )
            if existing_count:
                pytest.skip("Refusing to alter a data-bearing integration agent_run_events table.")

            await connection.execute("DROP TABLE IF EXISTS public.agent_run_events")
            assert await upgrade(connection) == "missing"

            await connection.execute("CREATE TABLE public.agent_run_events (id integer primary key)")
            assert await upgrade(connection) == "dropped"

            await connection.execute("CREATE TABLE public.agent_run_events (id integer primary key)")
            await connection.execute("INSERT INTO public.agent_run_events (id) VALUES (1)")
            with pytest.raises(RuntimeError, match="not empty"):
                await upgrade(connection)
        finally:
            await transaction.rollback()
            await connection.close()

    asyncio.run(exercise())

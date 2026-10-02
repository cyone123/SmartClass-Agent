from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

import app.core.chat_run_events as chat_run_events_module
from app import config
from app.core.chat_run_events import (
    ChatRunEventStoreUnavailable,
    ChatRunRedis,
    chat_run_redis_keys,
)
from app.core.chat_runs import _TokenEventBuffer


@pytest.fixture
def redis_store():
    server = fakeredis.FakeServer()
    command = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    reader = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    store = ChatRunRedis(
        command,
        reader,
        environment="test",
        key_prefix="sc",
        active_ttl_seconds=120,
        terminal_retention_seconds=60,
        operation_timeout_seconds=0.1,
        read_block_ms=10,
        read_batch_size=20,
    )
    yield store
    asyncio.run(store.close())


def test_redis_configuration_accepts_valid_values_and_rejects_invalid(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/2")
    monkeypatch.setenv("REDIS_KEY_PREFIX", "school")
    monkeypatch.setenv("REDIS_READER_POOL_SIZE", "25")
    monkeypatch.setenv("REDIS_ACTIVE_TTL_SECONDS", "3600")
    assert config.get_redis_url() == "redis://redis:6379/2"
    assert config.get_redis_key_prefix() == "school"
    assert config.get_redis_reader_pool_size() == 25
    assert config.get_redis_active_ttl_seconds() == 3600

    monkeypatch.setenv("REDIS_URL", "http://redis:6379")
    with pytest.raises(ValueError, match="REDIS_URL"):
        config.get_redis_url()
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("REDIS_ACTIVE_TTL_SECONDS", "0")
    with pytest.raises(ValueError, match="REDIS_ACTIVE_TTL_SECONDS"):
        config.get_redis_active_ttl_seconds()


def test_run_keys_are_deterministic_and_cluster_colocated() -> None:
    keys = chat_run_redis_keys("abc123", prefix="sc", environment="docker")
    assert keys == chat_run_redis_keys("abc123", prefix="sc", environment="docker")
    assert "{abc123}" in keys.stream
    assert "{abc123}" in keys.metadata
    assert "{abc123}" in keys.output
    assert len({key[key.index("{") : key.index("}") + 1] for key in vars(keys).values()}) == 1


def test_readiness_error_is_sanitized() -> None:
    class FailingRedis:
        async def ping(self):
            raise RedisConnectionError("redis://secret:password@example/0 sc:prod:chat-run:{private}:events")

    store = ChatRunRedis(FailingRedis(), FailingRedis(), environment="prod", operation_timeout_seconds=0.01)
    with pytest.raises(ChatRunEventStoreUnavailable) as captured:
        asyncio.run(store.ensure_ready())
    message = str(captured.value)
    assert "redis://" not in message
    assert "private" not in message
    assert "password" not in message


def test_configured_clients_use_separate_bounded_pools(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("REDIS_COMMAND_POOL_SIZE", "7")
    monkeypatch.setenv("REDIS_READER_POOL_SIZE", "11")
    monkeypatch.setenv("REDIS_OPERATION_TIMEOUT_SECONDS", "0.25")
    store = ChatRunRedis.from_config(environment="test")
    assert store.command_client.connection_pool is not store.reader_client.connection_pool
    assert store.command_client.connection_pool.max_connections == 7
    assert store.reader_client.connection_pool.max_connections == 11
    assert store.operation_timeout_seconds == 0.25
    asyncio.run(store.close())


def test_atomic_concurrent_append_has_unique_sequences_and_exact_output(redis_store: ChatRunRedis) -> None:
    async def exercise() -> None:
        await redis_store.start()
        sequences = await asyncio.gather(
            *(redis_store.append("run-1", "token", {"run_id": "run-1", "text": str(index)}) for index in range(40))
        )
        assert sorted(sequences) == list(range(1, 41))
        events = await redis_store.read_after("run-1", 0, block_ms=0, limit=100)
        snapshot = await redis_store.get_snapshot("run-1")
        assert snapshot is not None
        assert snapshot.last_sequence == 40
        assert snapshot.output_text == "".join(event.payload["text"] for event in events)

    asyncio.run(exercise())


def test_lua_scripts_reload_after_redis_script_cache_is_flushed(redis_store: ChatRunRedis) -> None:
    async def exercise() -> None:
        await redis_store.start()
        assert await redis_store.append("run-script-reload", "progress", {"step": 1}) == 1
        await redis_store.command_client.script_flush()
        assert await redis_store.append("run-script-reload", "progress", {"step": 2}) == 2
        await redis_store.command_client.script_flush()
        assert await redis_store.append_done("run-script-reload", sequence=3, status="succeeded") is True

    asyncio.run(exercise())


def test_replay_cursor_bounds_malformed_entries_and_independent_readers(redis_store: ChatRunRedis) -> None:
    async def exercise() -> None:
        await redis_store.start()
        for index in range(1, 6):
            await redis_store.append("run-2", "progress", {"index": index})
        keys = redis_store.keys("run-2")
        await redis_store.command_client.xadd(
            keys.stream,
            {"event": "unsupported", "data": "{}", "created_at": "bad"},
            id="6-0",
        )
        first = await redis_store.read_after("run-2", 0, block_ms=0, limit=2)
        middle = await redis_store.read_after("run-2", 2, block_ms=0, limit=20)
        reader_a, reader_b = await asyncio.gather(
            redis_store.read_after("run-2", 0, block_ms=0, limit=20),
            redis_store.read_after("run-2", 0, block_ms=0, limit=20),
        )
        assert [event.sequence for event in first] == [1, 2]
        assert [event.sequence for event in middle] == [3, 4, 5]
        assert [event.sequence for event in reader_a] == [1, 2, 3, 4, 5]
        assert reader_a == reader_b

    asyncio.run(exercise())


def test_snapshot_terminal_retention_cleanup_and_no_stream_trimming(redis_store: ChatRunRedis) -> None:
    async def exercise() -> None:
        await redis_store.start()
        assert await redis_store.get_snapshot("missing") is None
        for index in range(50):
            await redis_store.append("run-3", "token", {"text": "x", "index": index})
        keys = redis_store.keys("run-3")
        assert await redis_store.command_client.xlen(keys.stream) == 50
        assert await redis_store.append_done("run-3", sequence=51, status="succeeded") is True
        assert await redis_store.append_done("run-3", sequence=51, status="succeeded") is False
        entries = await redis_store.read_after("run-3", 50, block_ms=0)
        assert [(entry.sequence, entry.event_type) for entry in entries] == [(51, "done")]
        for key in vars(keys).values():
            ttl = await redis_store.command_client.ttl(key)
            assert 0 < ttl <= 60
        assert await redis_store.cleanup("run-3") == 3
        assert await redis_store.get_snapshot("run-3") is None

    asyncio.run(exercise())


def test_token_buffer_flushes_on_size_time_and_event_boundary() -> None:
    published: list[tuple[str, str]] = []
    sequence = 0

    async def publish(event_type: str, payload: dict) -> int:
        nonlocal sequence
        sequence += 1
        published.append((event_type, payload.get("text", "")))
        return sequence

    async def exercise() -> None:
        size_buffer = _TokenEventBuffer("run", publish, interval_ms=1000, max_chars=3)
        await size_buffer.add("a")
        await size_buffer.add("bc")
        await size_buffer.close()

        time_buffer = _TokenEventBuffer("run", publish, interval_ms=5, max_chars=100)
        await time_buffer.add("d")
        await asyncio.sleep(0.02)
        await time_buffer.close()

        boundary_buffer = _TokenEventBuffer("run", publish, interval_ms=1000, max_chars=100)
        await boundary_buffer.add("e")
        await boundary_buffer.add("f")
        await boundary_buffer.flush(reason="event_boundary")
        await publish("progress", {})
        await boundary_buffer.close()

    asyncio.run(exercise())
    assert published == [("token", "abc"), ("token", "d"), ("token", "ef"), ("progress", "")]


def test_capacity_and_pool_exhaustion_emit_explicit_sanitized_categories(monkeypatch) -> None:
    class Sink:
        def __init__(self) -> None:
            self.events = []

        def emit(self, event) -> None:
            self.events.append(event)

    sink = Sink()
    monkeypatch.setattr(chat_run_events_module, "get_observation_sink", lambda: sink)
    store = ChatRunRedis(object(), object(), environment="test", operation_timeout_seconds=0.01)

    async def oom():
        raise ResponseError("OOM command not allowed; redis://private")

    async def exhausted():
        raise RedisConnectionError("No connection available from private pool")

    async def exercise() -> None:
        with pytest.raises(ChatRunEventStoreUnavailable):
            await store._command("readiness", oom, unavailable=True)
        with pytest.raises(ChatRunEventStoreUnavailable):
            await store._command("readiness", exhausted, unavailable=True)

    asyncio.run(exercise())
    failed = [event for event in sink.events if event.status == "failed"]
    assert {event.fields["error_category"] for event in failed} == {
        "capacity_rejected",
        "connection_unavailable",
    }
    assert all("redis://" not in str(event.to_dict()) for event in failed)
    assert all("private pool" not in str(event.to_dict()) for event in failed)

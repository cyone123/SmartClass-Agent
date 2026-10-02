from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

from fastapi import Request
from redis.asyncio import BlockingConnectionPool, ConnectionPool, Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import NoScriptError, RedisError, ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.config import (
    get_redis_active_ttl_seconds,
    get_redis_append_max_retries,
    get_redis_command_pool_size,
    get_redis_key_prefix,
    get_redis_operation_timeout_seconds,
    get_redis_read_batch_size,
    get_redis_read_block_ms,
    get_redis_reader_pool_size,
    get_redis_terminal_retention_seconds,
    get_redis_url,
)
from app.core.observability import RunContext, get_observation_sink, log_observation, record_metric

SUPPORTED_EVENT_TYPES = frozenset(
    {
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
)

_APPEND_SCRIPT = """
local sequence = redis.call('HINCRBY', KEYS[2], 'last_sequence', 1)
local stream_id = tostring(sequence) .. '-0'
redis.call('XADD', KEYS[1], stream_id,
  'event', ARGV[1], 'data', ARGV[2], 'created_at', ARGV[3])
if ARGV[1] == 'token' and ARGV[4] ~= '' then
  redis.call('APPEND', KEYS[3], ARGV[4])
end
for _, key in ipairs(KEYS) do
  redis.call('EXPIRE', key, tonumber(ARGV[5]))
end
return sequence
"""

_TERMINAL_SCRIPT = """
local target = tonumber(ARGV[1])
local current = tonumber(redis.call('HGET', KEYS[2], 'last_sequence') or '0')
if current > target then
  return -1
end
if current == target then
  local existing = redis.call('XRANGE', KEYS[1], ARGV[1] .. '-0', ARGV[1] .. '-0', 'COUNT', 1)
  if #existing > 0 then
    return 0
  end
  return -1
end
if current ~= target - 1 and current ~= 0 then
  return -1
end
redis.call('XADD', KEYS[1], ARGV[1] .. '-0',
  'event', 'done', 'data', ARGV[2], 'created_at', ARGV[3])
redis.call('HSET', KEYS[2], 'last_sequence', target)
for _, key in ipairs(KEYS) do
  redis.call('EXPIRE', key, tonumber(ARGV[4]))
end
return 1
"""

T = TypeVar("T")


class ChatRunEventStoreError(RuntimeError):
    """Sanitized Redis transport failure safe to surface outside this module."""


class ChatRunEventStoreUnavailable(ChatRunEventStoreError):
    pass


@dataclass(frozen=True)
class ChatRunEvent:
    run_id: str
    sequence: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class ChatRunLiveSnapshot:
    last_sequence: int
    output_text: str


@dataclass(frozen=True)
class ChatRunRedisKeys:
    stream: str
    metadata: str
    output: str


def chat_run_redis_keys(run_id: str, *, prefix: str | None = None, environment: str | None = None) -> ChatRunRedisKeys:
    normalized_run_id = str(run_id).strip()
    if not normalized_run_id or any(character in normalized_run_id for character in "{}\r\n\t "):
        raise ValueError("run_id is not valid for chat run event storage.")
    normalized_prefix = (prefix or get_redis_key_prefix()).strip().strip(":")
    normalized_environment = (environment or "local").strip().lower().replace(":", "-")
    if not normalized_environment or any(character in normalized_environment for character in "{}\r\n\t "):
        raise ValueError("Redis environment prefix is invalid.")
    base = f"{normalized_prefix}:{normalized_environment}:chat-run:{{{normalized_run_id}}}"
    return ChatRunRedisKeys(stream=f"{base}:events", metadata=f"{base}:meta", output=f"{base}:output")


class ChatRunRedis:
    def __init__(
        self,
        command_client: Redis,
        reader_client: Redis,
        *,
        environment: str,
        key_prefix: str | None = None,
        active_ttl_seconds: int | None = None,
        terminal_retention_seconds: int | None = None,
        operation_timeout_seconds: float | None = None,
        read_block_ms: int | None = None,
        read_batch_size: int | None = None,
        append_max_retries: int | None = None,
    ) -> None:
        self.command_client = command_client
        self.reader_client = reader_client
        self.environment = environment
        self.key_prefix = key_prefix or get_redis_key_prefix()
        self.active_ttl_seconds = active_ttl_seconds or get_redis_active_ttl_seconds()
        self.terminal_retention_seconds = terminal_retention_seconds or get_redis_terminal_retention_seconds()
        self.operation_timeout_seconds = operation_timeout_seconds or get_redis_operation_timeout_seconds()
        self.read_block_ms = read_block_ms or get_redis_read_block_ms()
        self.read_batch_size = read_batch_size or get_redis_read_batch_size()
        self.append_max_retries = get_redis_append_max_retries() if append_max_retries is None else append_max_retries
        self._append_sha: str | None = None
        self._terminal_sha: str | None = None
        self._closed = False

    @classmethod
    def from_config(cls, *, environment: str) -> "ChatRunRedis":
        url = get_redis_url()
        timeout = get_redis_operation_timeout_seconds()
        common = {
            "decode_responses": True,
            "socket_connect_timeout": timeout,
            "socket_timeout": timeout,
            "health_check_interval": 30,
        }
        command_pool = ConnectionPool.from_url(
            url,
            max_connections=get_redis_command_pool_size(),
            **common,
        )
        reader_pool = BlockingConnectionPool.from_url(
            url,
            max_connections=get_redis_reader_pool_size(),
            timeout=timeout,
            decode_responses=True,
            socket_connect_timeout=timeout,
            socket_timeout=(get_redis_read_block_ms() / 1000) + timeout,
            health_check_interval=30,
        )
        return cls(
            Redis(connection_pool=command_pool),
            Redis(connection_pool=reader_pool),
            environment=environment,
            operation_timeout_seconds=timeout,
        )

    def keys(self, run_id: str) -> ChatRunRedisKeys:
        return chat_run_redis_keys(
            run_id,
            prefix=self.key_prefix,
            environment=self.environment,
        )

    async def start(self) -> None:
        await self.ensure_ready()
        self._append_sha = await self._command("script_load", lambda: self.command_client.script_load(_APPEND_SCRIPT))
        self._terminal_sha = await self._command(
            "script_load", lambda: self.command_client.script_load(_TERMINAL_SCRIPT)
        )

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await asyncio.gather(self.command_client.aclose(), self.reader_client.aclose(), return_exceptions=True)

    async def ensure_ready(self) -> None:
        await self._command("readiness", self.command_client.ping, unavailable=True)

    async def append(self, run_id: str, event_type: str, payload: dict[str, Any]) -> int:
        if event_type not in SUPPORTED_EVENT_TYPES or event_type == "done":
            raise ValueError(f"Unsupported chat run event type: {event_type}")
        keys = self.keys(run_id)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        token_text = payload.get("text") if event_type == "token" else ""
        if not isinstance(token_text, str):
            token_text = ""

        async def execute() -> int:
            if self._append_sha is None:
                self._append_sha = await self.command_client.script_load(_APPEND_SCRIPT)
            try:
                result = await self.command_client.evalsha(
                    self._append_sha,
                    3,
                    keys.stream,
                    keys.metadata,
                    keys.output,
                    event_type,
                    encoded,
                    datetime.now(timezone.utc).isoformat(),
                    token_text,
                    self.active_ttl_seconds,
                )
            except NoScriptError:
                self._append_sha = await self.command_client.script_load(_APPEND_SCRIPT)
                result = await self.command_client.evalsha(
                    self._append_sha,
                    3,
                    keys.stream,
                    keys.metadata,
                    keys.output,
                    event_type,
                    encoded,
                    datetime.now(timezone.utc).isoformat(),
                    token_text,
                    self.active_ttl_seconds,
                )
            return int(result)

        sequence = await self._command(
            "append",
            execute,
            run_id=run_id,
            event_type=event_type,
            payload_size=len(encoded.encode("utf-8")),
            retries=self.append_max_retries,
        )
        return sequence

    async def read_after(
        self,
        run_id: str,
        after_sequence: int,
        *,
        block_ms: int | None = None,
        limit: int | None = None,
    ) -> list[ChatRunEvent]:
        keys = self.keys(run_id)
        cursor = max(int(after_sequence), 0)
        count = limit or self.read_batch_size
        wait_ms = self.read_block_ms if block_ms is None else max(block_ms, 0)

        async def execute() -> Any:
            if wait_ms:
                return await self.reader_client.xread(
                    {keys.stream: f"{cursor}-0"},
                    count=count,
                    block=wait_ms,
                )
            rows = await self.reader_client.xrange(keys.stream, min=f"({cursor}-0", max="+", count=count)
            return [(keys.stream, rows)] if rows else []

        raw = await self._reader(
            "blocking_wait" if wait_ms else "replay",
            execute,
            run_id=run_id,
            reconnect=cursor > 0,
        )
        events: list[ChatRunEvent] = []
        malformed = 0
        for _stream, rows in raw or []:
            for stream_id, values in rows:
                decoded = self._decode_event(run_id, stream_id, values)
                if decoded is None:
                    malformed += 1
                    continue
                events.append(decoded)
        if malformed:
            self._observe(
                "decode",
                run_id=run_id,
                status="failed",
                fields={"error_category": "malformed_entry", "malformed_count": malformed},
            )
        if events:
            self._observe(
                "replay",
                run_id=run_id,
                fields={"event_count": len(events), "reconnect": cursor > 0},
            )
        return events

    async def get_snapshot(self, run_id: str) -> ChatRunLiveSnapshot | None:
        keys = self.keys(run_id)

        async def execute() -> tuple[Any, Any]:
            async with self.command_client.pipeline(transaction=False) as pipeline:
                pipeline.hget(keys.metadata, "last_sequence")
                pipeline.get(keys.output)
                sequence, output = await pipeline.execute()
            return sequence, output

        sequence, output = await self._command("snapshot", execute, run_id=run_id)
        if sequence is None and output is None:
            return None
        return ChatRunLiveSnapshot(last_sequence=int(sequence or 0), output_text=str(output or ""))

    async def append_done(self, run_id: str, *, sequence: int, status: str) -> bool:
        if sequence < 1:
            raise ValueError("Terminal sequence must be positive.")
        keys = self.keys(run_id)
        payload = json.dumps({"run_id": run_id, "status": status}, ensure_ascii=False, separators=(",", ":"))

        async def execute() -> int:
            if self._terminal_sha is None:
                self._terminal_sha = await self.command_client.script_load(_TERMINAL_SCRIPT)
            try:
                result = await self.command_client.evalsha(
                    self._terminal_sha,
                    3,
                    keys.stream,
                    keys.metadata,
                    keys.output,
                    sequence,
                    payload,
                    datetime.now(timezone.utc).isoformat(),
                    self.terminal_retention_seconds,
                )
            except NoScriptError:
                self._terminal_sha = await self.command_client.script_load(_TERMINAL_SCRIPT)
                result = await self.command_client.evalsha(
                    self._terminal_sha,
                    3,
                    keys.stream,
                    keys.metadata,
                    keys.output,
                    sequence,
                    payload,
                    datetime.now(timezone.utc).isoformat(),
                    self.terminal_retention_seconds,
                )
            return int(result)

        result = await self._command("terminal", execute, run_id=run_id, event_type="done")
        if result < 0:
            raise ChatRunEventStoreError("Chat run terminal event sequence is inconsistent.")
        return result == 1

    async def apply_terminal_retention(self, run_id: str) -> None:
        keys = self.keys(run_id)

        async def execute() -> None:
            async with self.command_client.pipeline(transaction=True) as pipeline:
                for key in (keys.stream, keys.metadata, keys.output):
                    pipeline.expire(key, self.terminal_retention_seconds)
                await pipeline.execute()

        await self._command("retention", execute, run_id=run_id)

    async def cleanup(self, run_id: str) -> int:
        keys = self.keys(run_id)
        deleted = await self._command(
            "cleanup",
            lambda: self.command_client.delete(keys.stream, keys.metadata, keys.output),
            run_id=run_id,
        )
        return int(deleted)

    def _decode_event(self, run_id: str, stream_id: Any, values: Any) -> ChatRunEvent | None:
        try:
            sequence_text = str(stream_id).split("-", 1)[0]
            sequence = int(sequence_text)
            event_type = str(values["event"])
            if sequence < 1 or event_type not in SUPPORTED_EVENT_TYPES:
                return None
            payload = json.loads(values["data"])
            if not isinstance(payload, dict):
                return None
            created_at = datetime.fromisoformat(values["created_at"])
            return ChatRunEvent(
                run_id=run_id,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
                created_at=created_at,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    async def _command(
        self,
        operation: str,
        callback: Callable[[], Awaitable[T]],
        *,
        run_id: str = "redis",
        unavailable: bool = False,
        retries: int = 0,
        event_type: str | None = None,
        payload_size: int | None = None,
    ) -> T:
        return await self._execute(
            operation,
            callback,
            run_id=run_id,
            unavailable=unavailable,
            retries=retries,
            event_type=event_type,
            payload_size=payload_size,
        )

    async def _reader(
        self,
        operation: str,
        callback: Callable[[], Awaitable[T]],
        *,
        run_id: str,
        reconnect: bool,
    ) -> T:
        return await self._execute(operation, callback, run_id=run_id, reconnect=reconnect)

    async def _execute(
        self,
        operation: str,
        callback: Callable[[], Awaitable[T]],
        *,
        run_id: str,
        unavailable: bool = False,
        retries: int = 0,
        event_type: str | None = None,
        payload_size: int | None = None,
        reconnect: bool = False,
    ) -> T:
        started = time.perf_counter()
        last_error: BaseException | None = None
        for attempt in range(retries + 1):
            try:
                result = await callback()
                duration_ms = int((time.perf_counter() - started) * 1000)
                fields: dict[str, Any] = {
                    "operation": operation,
                    "event_type": event_type,
                    "payload_size_bytes": payload_size,
                    "retry_count": attempt,
                    "reconnect": reconnect,
                }
                self._observe(operation, run_id=run_id, duration_ms=duration_ms, fields=fields)
                return result
            except (RedisConnectionError, RedisTimeoutError, RedisError) as exc:
                last_error = exc
                if attempt < retries:
                    await asyncio.sleep(min(0.05 * (2**attempt), self.operation_timeout_seconds))
        duration_ms = int((time.perf_counter() - started) * 1000)
        error_category = self._redis_error_category(last_error)
        self._observe(
            operation,
            run_id=run_id,
            status="failed",
            duration_ms=duration_ms,
            fields={
                "operation": operation,
                "error_category": error_category,
                "error_type": last_error.__class__.__name__ if last_error else "RedisError",
                "retry_count": retries,
            },
        )
        if unavailable:
            raise ChatRunEventStoreUnavailable("Chat run event storage is unavailable.") from None
        raise ChatRunEventStoreError("Chat run event storage operation failed.") from None

    def _observe(
        self,
        operation: str,
        *,
        run_id: str,
        status: str = "success",
        duration_ms: int | None = None,
        fields: dict[str, Any] | None = None,
    ) -> None:
        context = RunContext(run_id=run_id, agent_name="chat_run_redis")
        event_name = f"chat.redis.{operation}"
        safe_fields = {key: value for key, value in (fields or {}).items() if value is not None}
        record_metric(
            event_name,
            context=context,
            sink=get_observation_sink(),
            status=status,
            duration_ms=duration_ms,
            fields=safe_fields,
        )
        if status == "failed":
            log_observation(
                event_name,
                context=context,
                sink=get_observation_sink(),
                status="failed",
                fields=safe_fields,
            )

    @staticmethod
    def _redis_error_category(error: BaseException | None) -> str:
        if isinstance(error, RedisTimeoutError):
            return "timeout"
        if isinstance(error, ResponseError) and "OOM" in str(error).upper():
            return "capacity_rejected"
        if isinstance(error, RedisConnectionError) and "connection" in str(error).lower():
            return "connection_unavailable"
        return "redis_error"


def get_chat_run_redis(request: Request) -> ChatRunRedis:
    store = getattr(request.app.state, "chat_run_redis", None)
    if store is None:
        raise RuntimeError("Chat run Redis transport is not initialized.")
    return store

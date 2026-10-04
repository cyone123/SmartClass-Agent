from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock

import httpx
from langchain_core.language_models import BaseChatModel

from .adapters.openai_chat import build_model
from .config_repository import ConfigRepository, load_configuration
from .registry import validate_capabilities, validate_parameters
from .schemas import ConfigError, ResolvedModelConfigSnapshot, restore_snapshot
from .secrets import SecretResolver

_active: ContextVar[ResolvedModelConfigSnapshot | None] = ContextVar("model_configuration", default=None)
_published: ResolvedModelConfigSnapshot | None = None


def current_snapshot() -> ResolvedModelConfigSnapshot:
    # Return an isolated copy: nested dicts on Pydantic frozen models are not immutable.
    snapshot = _active.get() or _published or load_configuration()
    return restore_snapshot(snapshot.model_dump(mode="json"))


def initialize(repository: ConfigRepository | None = None) -> ResolvedModelConfigSnapshot:
    global _published
    snapshot = repository.load() if repository else load_configuration()
    for role in ("main", "structured", "small", "structured_fast", "memory"):
        if role not in snapshot.roles or not snapshot.roles[role].enabled:
            raise ConfigError(f"{role}: required role is not configured")
        connection = snapshot.connections[snapshot.models[snapshot.roles[role].model].connection]
        factory.secrets.resolve(connection.credential)
    _published = restore_snapshot(snapshot.model_dump(mode="json"))
    return current_snapshot()


@contextmanager
def use_snapshot(snapshot: ResolvedModelConfigSnapshot | dict):
    parsed = restore_snapshot(snapshot if isinstance(snapshot, dict) else snapshot.model_dump(mode="json"))
    token = _active.set(parsed)
    try:
        yield parsed
    finally:
        _active.reset(token)


class ModelFactory:
    """Own clients per event loop and credential generation; bindings are never cached."""

    def __init__(self, secrets: SecretResolver | None = None):
        self.secrets = secrets or SecretResolver()
        self._clients: dict[tuple, tuple[httpx.Client, httpx.AsyncClient]] = {}
        self._lock = RLock()

    def get(
        self, role: str, *, streaming: bool = False, snapshot: ResolvedModelConfigSnapshot | None = None
    ) -> BaseChatModel:
        snapshot = snapshot or current_snapshot()
        binding = snapshot.roles.get(role)
        if binding is None or not binding.enabled:
            raise ConfigError(f"{role}: role is unavailable or disabled")
        profile = snapshot.models[binding.model]
        connection = snapshot.connections[profile.connection]
        validate_capabilities(role, profile, streaming=streaming)
        validate_parameters(profile, connection)
        builder = build_model
        if connection.protocol == "anthropic_messages":
            from .adapters.anthropic_messages import build_model as builder
        elif connection.protocol == "google_genai":
            from .adapters.google_genai import build_model as builder
        key, generation = self.secrets.resolve(connection.credential)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        cache_key = (
            snapshot.fingerprint,
            binding.model,
            streaming,
            generation,
            object() if loop is None else None,
            loop,
        )
        with self._lock:
            if cache_key not in self._clients:
                self._clients[cache_key] = self._new_clients()
            sync_client, async_client = self._clients[cache_key]
        model = builder(
            profile, connection, api_key=key, streaming=streaming, sync_client=sync_client, async_client=async_client
        )

        model.metadata = {
            **(model.metadata or {}),
            "smartclass_provider": connection.preset,
            "smartclass_protocol": connection.protocol,
            "smartclass_model_id": profile.model_id,
            "smartclass_configuration_version": snapshot.fingerprint,
            "smartclass_capability_rules_version": snapshot.rules_version,
            "smartclass_actual_upstream": "unknown",
            "smartclass_capabilities": profile.capabilities.model_dump(),
            "smartclass_structured_method": profile.parameters.structured_method,
        }
        return model

    def _new_clients(self):
        return httpx.Client(), httpx.AsyncClient()

    async def close(self) -> None:
        # Application calls this in the owning loop before it shuts down.
        loop = asyncio.get_running_loop()
        with self._lock:
            entries = [(key, pair) for key, pair in self._clients.items() if key[-1] in (None, loop)]
            for key, _ in entries:
                self._clients.pop(key)
        for _, (sync_client, async_client) in entries:
            sync_client.close()
            await async_client.aclose()


factory = ModelFactory()


def get_role_model(role: str, *, streaming: bool = False) -> BaseChatModel:
    return factory.get(role, streaming=streaming)


async def shutdown() -> None:
    global _published
    await factory.close()
    _published = None

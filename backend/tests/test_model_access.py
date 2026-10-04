from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.model_access.config_repository import (
    EnvConfigRepository,
    FileConfigRepository,
    InMemoryConfigRepository,
    resolve,
)
from app.core.model_access.factory import ModelFactory, current_snapshot, initialize, shutdown, use_snapshot
from app.core.model_access.schemas import ConfigError, Configuration, ensure_snapshot_protocols, restore_snapshot
from app.core.model_access.secrets import SecretResolver


def environment():
    return {
        "MODEL": "main-a",
        "API_KEY": "secret-a",
        "BASE_URL": "https://a.example/v1",
        "STRUCTURED_MODEL": "structured-a",
        "STRUCTURED_API_KEY": "secret-s",
        "STRUCTURED_BASE_URL": "https://s.example/v1",
        "SMALL_MODEL": "small-a",
        "SMALL_API_KEY": "secret-b",
        "SMALL_BASE_URL": "https://b.example/v1",
    }


def test_legacy_whole_identity_and_original_order():
    snapshot = EnvConfigRepository(environment()).load()
    memory = snapshot.models[snapshot.roles["memory"].model]
    assert memory.model_id == "structured-a"  # An absent fast identity must not outrank structured.
    assert snapshot.connections[memory.connection].credential == "env:STRUCTURED_API_KEY"
    assert snapshot.connections[memory.connection].endpoint == "https://s.example/v1"
    env = environment()
    for name in list(env):
        if name.startswith("SMALL_"):
            del env[name]
    snapshot = EnvConfigRepository(env).load()
    assert snapshot.models[snapshot.roles["memory"].model].model_id == "structured-a"
    assert "small" not in snapshot.roles


@pytest.mark.parametrize("role", ["MEMORY", "CONTEXT_COMPRESSION", "STRUCTURED_FAST", "VIDEO_VISION"])
def test_partial_identity_fails_without_borrowing_credentials(role):
    env = environment() | {role + "_MODEL": "private-model", "CONTEXT_COMPRESSION_ENABLED": "true"}
    with pytest.raises(ConfigError, match=role + "_API_KEY") as error:
        EnvConfigRepository(env).load()
    assert "secret" not in str(error.value)
    assert "private-model" not in str(error.value)


def test_disabled_optional_roles_do_not_require_credentials():
    env = environment() | {
        "VIDEO_VISION_ENABLED": "false",
        "VIDEO_VISION_MODEL": "unused",
        "CONTEXT_COMPRESSION_MODEL": "unused",
    }
    snapshot = EnvConfigRepository(env).load()
    assert not snapshot.roles["compression"].enabled
    assert not snapshot.roles["video_vision"].enabled


@pytest.mark.parametrize("prefix", ["MEMORY", "CONTEXT_COMPRESSION", "STRUCTURED_FAST", "VIDEO_VISION"])
def test_dedicated_identity_without_endpoint_cannot_change_provider_silently(prefix):
    env = environment() | {
        prefix + "_MODEL": "dedicated",
        prefix + "_API_KEY": "private",
        "CONTEXT_COMPRESSION_ENABLED": "true",
    }
    with pytest.raises(ConfigError, match=prefix + "_BASE_URL"):
        EnvConfigRepository(env).load()


@pytest.mark.parametrize(
    "raw",
    [
        {"version": 9},
        {"roles": {"main": {"model": "a", "inherit": "small"}}},
        {"roles": {"main": {"inherit": "small"}, "small": {"inherit": "main"}}},
        {"connections": {"a": {"preset": "openai", "credential": "plain-secret"}}},
        {"connections": {"a": {"preset": "openai", "credential": "env:KEY", "endpoint": "https://a/?key=secret"}}},
        {"connections": {"a": {"preset": "openai", "credential": "env:KEY", "protocol": "google_genai"}}},
        {"models": {"a": {"connection": "missing", "model_id": "a"}}},
        {"models": {"a": {"connection": "missing", "model_id": "a", "parameters": {"api_key": "secret"}}}},
    ],
)
def test_invalid_schema_and_references(raw):
    with pytest.raises((ValidationError, ConfigError)):
        resolve(Configuration.model_validate(raw))


def test_file_precedence_paths_and_public_snapshot(tmp_path):
    source = Path(__file__).resolve().parents[2] / "model-config.example.yaml"
    (tmp_path / "config.yaml").write_text(source.read_text(), encoding="utf-8")
    env = environment() | {"MEMORY_MODEL": "partial", "MODEL_THINKING_MODE": "invalid"}
    snapshot = FileConfigRepository("config.yaml", root=tmp_path, environ=env).load()
    assert snapshot == FileConfigRepository(tmp_path / "config.yaml", environ=env).load()
    assert snapshot.models[snapshot.roles["main"].model].model_id == "gpt-4o-mini"
    restored = restore_snapshot(json.loads(snapshot.model_dump_json()))
    assert restored == snapshot
    public = json.dumps(snapshot.public_dto())
    assert "https:" not in public and "env:" not in public and "secret" not in public
    assert "env:API_KEY" in snapshot.model_dump_json()
    assert "secret-a" not in snapshot.model_dump_json()
    corrupted = snapshot.model_dump()
    corrupted["models"]["teaching"]["model_id"] = "changed"
    with pytest.raises(ConfigError, match="fingerprint"):
        restore_snapshot(corrupted)
    with pytest.raises(ConfigError, match="MODEL_CONFIG_PATH"):
        FileConfigRepository("missing", root=tmp_path).load()


def test_unknown_capability_and_explicit_override():
    snapshot = EnvConfigRepository(environment()).load()
    raw = snapshot.model_dump(exclude={"fingerprint", "rules_version"})
    raw["models"]["legacy-main"]["capabilities"]["tools"] = None
    with pytest.raises(ConfigError, match="tools"):
        resolve(Configuration.model_validate(raw))

    raw["models"]["legacy-main"]["capabilities"]["tools"] = True
    assert resolve(Configuration.model_validate(raw))
    raw["models"]["legacy-main"]["capabilities"]["reasoning_roundtrip"] = True
    with pytest.raises(ConfigError, match="adapter"):
        resolve(Configuration.model_validate(raw))


def test_timeout_and_legacy_thinking_inheritance():
    env = environment() | {
        "SMALL_MODEL": "deepseek-test",
        "STRUCTURED_TIMEOUT_MS": "2500",
        "CONTEXT_COMPRESSION_ENABLED": "true",
        "CONTEXT_COMPRESSION_TIMEOUT_MS": "7000",
    }
    snapshot = EnvConfigRepository(env).load()
    assert snapshot.models[snapshot.roles["structured_fast"].model].parameters.thinking == "off"
    assert snapshot.models[snapshot.roles["memory"].model].parameters.timeout == 2.5
    assert snapshot.models[snapshot.roles["compression"].model].parameters.timeout == 7


def test_factory_isolation_rotation_bindings_and_lifecycle():
    env = environment()
    snapshot = EnvConfigRepository(env).load()
    factory = ModelFactory(SecretResolver(env))

    async def exercise():
        first = factory.get("main", snapshot=snapshot, streaming=True)
        assert first.stream_usage is True
        second = factory.get("main", snapshot=snapshot, streaming=False)
        assert first.http_async_client is not second.http_async_client
        tool_a = {"name": "a", "description": "a", "parameters": {"type": "object", "properties": {}}}
        tool_b = {"name": "b", "description": "b", "parameters": {"type": "object", "properties": {}}}
        a, b = first.bind_tools([tool_a]), first.bind_tools([tool_b])
        assert a.kwargs["tools"] != b.kwargs["tools"]
        env["API_KEY"] = "rotated"
        rotated = factory.get("main", snapshot=snapshot, streaming=True)
        assert rotated.http_async_client is not first.http_async_client
        assert rotated.openai_api_key.get_secret_value() == "rotated"
        del env["API_KEY"]
        with pytest.raises(ConfigError, match="unavailable"):
            factory.get("main", snapshot=snapshot)
        await factory.close()
        assert first.http_client.is_closed and first.http_async_client.is_closed
        return first.http_async_client

    old = asyncio.run(exercise())
    env["API_KEY"] = "next"

    async def another_loop():
        model = factory.get("main", snapshot=snapshot)
        assert model.http_async_client is not old
        await factory.close()

    asyncio.run(another_loop())


def test_startup_freezes_config_and_context_isolated(monkeypatch):
    env = environment()
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    repository = EnvConfigRepository(env)
    snapshot = initialize(repository)
    monkeypatch.setenv("MODEL", "new-model")
    assert current_snapshot().fingerprint == snapshot.fingerprint
    newer = EnvConfigRepository(env | {"MODEL": "new-model"}).load()
    with use_snapshot(newer):
        assert current_snapshot().fingerprint == newer.fingerprint
    assert current_snapshot().fingerprint == snapshot.fingerprint
    asyncio.run(shutdown())


def test_in_memory_repository_is_storage_agnostic_and_returns_isolated_snapshots():
    snapshot = EnvConfigRepository(environment()).load()
    repository = InMemoryConfigRepository(snapshot)

    first = repository.load()
    first.roles["main"] = first.roles["small"]
    second = repository.load()

    assert second.fingerprint == snapshot.fingerprint
    assert second.roles["main"].model == snapshot.roles["main"].model
    factory = ModelFactory(SecretResolver(environment()))
    assert factory.get("main", snapshot=second).model_name == "main-a"
    asyncio.run(factory.close())


def test_legacy_runtime_preflight_rejects_new_protocol_snapshot():
    config = Configuration.model_validate(
        {
            "connections": {
                "native": {
                    "preset": "anthropic",
                    "protocol": "anthropic_messages",
                    "credential": "env:ANTHROPIC_API_KEY",
                }
            },
            "models": {
                "native": {
                    "connection": "native",
                    "model_id": "claude-test",
                    "capabilities": {"text": True, "streaming": True, "tools": True, "tool_choice": True},
                }
            },
            "roles": {role: {"model": "native"} for role in ("main", "structured", "small", "memory")},
        }
    )
    snapshot = resolve(config, {"ANTHROPIC_API_KEY": "test"})

    with pytest.raises(ConfigError, match="anthropic_messages"):
        ensure_snapshot_protocols(snapshot, frozenset({"openai_chat"}))


def test_file_inheritance_cannot_reach_legacy_identity(tmp_path):
    (tmp_path / "config.yaml").write_text("version: 1\nroles:\n  main: {inherit: small}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="small"):
        FileConfigRepository("config.yaml", root=tmp_path, environ=environment()).load()


def test_mixed_file_and_env_keeps_legacy_timeout_policy(tmp_path):
    (tmp_path / "config.yaml").write_text("version: 1\nroles:\n  video_vision: {enabled: false}\n", encoding="utf-8")
    env = environment() | {"SMALL_MODEL": "deepseek-test", "STRUCTURED_TIMEOUT_MS": "2500"}
    snapshot = FileConfigRepository("config.yaml", root=tmp_path, environ=env).load()
    fast = snapshot.models[snapshot.roles["structured_fast"].model]
    assert fast.parameters.timeout == 2.5 and fast.parameters.thinking == "off"
    assert snapshot.models[snapshot.roles["memory"].model].model_id == "structured-a"


def test_vision_connection_and_disabled_role_are_independent():
    from app.core.video_transcribe import VideoTranscriptionRuntime

    env = environment() | {
        "VIDEO_VISION_MODEL": "vision-b",
        "VIDEO_VISION_API_KEY": "vision-key",
        "VIDEO_VISION_BASE_URL": "https://vision.example/v1",
    }
    snapshot = EnvConfigRepository(env).load()
    factory = ModelFactory(SecretResolver(env))

    async def exercise():
        main = factory.get("main", snapshot=snapshot)
        vision = factory.get("video_vision", snapshot=snapshot)
        assert main.openai_api_key.get_secret_value() == "secret-a"
        assert vision.model_name == "vision-b" and str(vision.openai_api_base) == "https://vision.example/v1"
        assert vision.openai_api_key.get_secret_value() == "vision-key"
        await factory.close()

    asyncio.run(exercise())
    disabled = EnvConfigRepository(environment() | {"VIDEO_VISION_ENABLED": "false"}).load()
    with use_snapshot(disabled):
        runtime = VideoTranscriptionRuntime(speech_runtime=None)
        assert runtime.vision_config is None
        with pytest.raises(ConfigError, match="disabled"):
            runtime._get_vision_model()

from __future__ import annotations

from app.core.model_access.config_repository import resolve
from app.core.model_access.schemas import Configuration
from tests.evals.manifest import model_summary_from_environment, model_summary_from_snapshot, sanitize_model_summary


def test_model_summary_records_roles_without_credentials(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_CONFIG_PATH", raising=False)
    for name in (
        "MEMORY_MODEL",
        "MEMORY_API_KEY",
        "MEMORY_BASE_URL",
        "VIDEO_VISION_MODEL",
        "VIDEO_VISION_API_KEY",
        "VIDEO_VISION_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VIDEO_VISION_ENABLED", "false")
    monkeypatch.setenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("MODEL", "main-model")
    monkeypatch.setenv("STRUCTURED_MODEL", "structured-model")
    monkeypatch.setenv("SMALL_MODEL", "small-model")
    monkeypatch.setenv("STRUCTURED_FAST_MODEL", "fast-model")
    monkeypatch.setenv("STRUCTURED_FAST_API_KEY", "fast-secret")
    monkeypatch.setenv("STRUCTURED_FAST_BASE_URL", "https://fast.example/v1")
    monkeypatch.setenv("API_KEY", "must-not-appear")
    monkeypatch.setenv("SMALL_API_KEY", "also-secret")

    summary = model_summary_from_environment()

    assert summary["provider"] == "legacy"
    assert summary["model"] == "main-model"
    assert summary["models"] == {
        "main": "main-model",
        "structured": "structured-model",
        "structured_fast": "fast-model",
        "small": "small-model",
        "memory": "fast-model",
    }
    assert summary["roles"]["main"]["protocol"] == "openai_chat"
    assert summary["roles"]["main"]["actual_upstream"] == "unknown"
    assert summary["configuration_version"].startswith("v1:")
    assert "must-not-appear" not in str(summary)
    assert "also-secret" not in str(summary)
    assert "fast-secret" not in str(summary)
    assert "aliyuncs.com" not in str(summary)


def test_snapshot_summary_records_role_policies_and_actual_upstream_without_sensitive_fields() -> None:
    snapshot = resolve(
        Configuration.model_validate(
            {
                "version": 1,
                "connections": {
                    "router": {
                        "preset": "openrouter",
                        "protocol": "openai_chat",
                        "endpoint": "https://sensitive.example/v1",
                        "credential": "env:ROUTER_SECRET",
                    }
                },
                "models": {
                    "primary": {
                        "connection": "router",
                        "model_id": "vendor/model",
                        "parameters": {
                            "thinking": "on",
                            "reasoning_effort": "high",
                            "provider_routing": {"only": ["vendor-a"], "allow_fallbacks": False},
                        },
                        "capabilities": {
                            "text": True,
                            "streaming": True,
                            "tools": True,
                            "tool_choice": True,
                        },
                    }
                },
                "roles": {
                    role: {"model": "primary"} for role in ("main", "structured", "structured_fast", "small", "memory")
                },
            }
        ),
        {"ROUTER_SECRET": "not-serialized"},
    )

    summary = model_summary_from_snapshot(
        snapshot,
        {
            "main": {
                "smartclass_actual_upstream": "vendor-a",
                "smartclass_fallback_used": True,
                "smartclass_attempts": [{"provider": "openrouter", "protocol": "openai_chat", "model": "vendor/model"}],
                "authorization": "Bearer nope",
            }
        },
    )

    assert summary["roles"]["main"] == {
        "provider": "openrouter",
        "protocol": "openai_chat",
        "model": "vendor/model",
        "thinking": "on",
        "reasoning_effort": "high",
        "structured_method": "tool_calling",
        "provider_routing": {
            "only": ["vendor-a"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
        "capability_rules_version": "1",
        "actual_upstream": "vendor-a",
        "fallback": [],
        "fallback_used": True,
        "attempts": [{"provider": "openrouter", "protocol": "openai_chat", "model": "vendor/model"}],
    }
    serialized = str(summary)
    assert "sensitive.example" not in serialized
    assert "ROUTER_SECRET" not in serialized
    assert "not-serialized" not in serialized
    assert "Bearer nope" not in serialized


def test_sanitized_model_summary_keeps_thinking_and_routing_runs_distinct() -> None:
    base = {
        "configuration_version": "v1:test",
        "roles": {
            "main": {
                "provider": "openrouter",
                "protocol": "openai_chat",
                "model": "vendor/model",
                "thinking": "off",
                "provider_routing": {"allow_fallbacks": False, "require_parameters": True},
            }
        },
    }
    changed = {
        **base,
        "roles": {
            "main": {
                **base["roles"]["main"],
                "thinking": "on",
                "provider_routing": {"allow_fallbacks": True, "require_parameters": True},
            }
        },
    }
    assert sanitize_model_summary(base) != sanitize_model_summary(changed)

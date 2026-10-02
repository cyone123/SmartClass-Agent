from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

import yaml
from pydantic import ValidationError

from .registry import legacy_capabilities, resolve_connection, validate_capabilities, validate_parameters
from .schemas import (
    ConfigError,
    Configuration,
    Connection,
    ModelProfile,
    Parameters,
    ResolvedModelConfigSnapshot,
    RoleBinding,
    fingerprint,
)

PREFIXES = {
    "main": "",
    "structured": "STRUCTURED_",
    "small": "SMALL_",
    "structured_fast": "STRUCTURED_FAST_",
    "memory": "MEMORY_",
    "compression": "CONTEXT_COMPRESSION_",
    "video_vision": "VIDEO_VISION_",
}
INHERIT = {
    "structured_fast": ("small",),
    "memory": ("structured_fast", "structured", "small", "main"),
    "compression": ("memory", "structured_fast", "structured", "small", "main"),
    "video_vision": ("main",),
}
CONFIG_ROOT = Path(__file__).resolve().parents[4]


class ConfigRepository(Protocol):
    def load(self) -> ResolvedModelConfigSnapshot: ...


def _timeout(env: Mapping[str, str], name: str, default: str = "0") -> float | None:
    try:
        value = int(env.get(name, default) or default)
    except ValueError:
        raise ConfigError(f"{name} must be an integer") from None
    return value / 1000 if value > 0 else None


class EnvConfigRepository:
    def __init__(self, environ: Mapping[str, str] | None = None):
        self.environ = dict(environ if environ is not None else os.environ)

    def configuration(self, explicit: Configuration | None = None) -> Configuration:
        config = (explicit or Configuration()).model_dump(mode="python")
        env = self.environ
        for role, prefix in PREFIXES.items():
            if role in config["roles"]:
                continue
            if role in {"compression", "video_vision"}:
                flag = "CONTEXT_COMPRESSION_ENABLED" if role == "compression" else "VIDEO_VISION_ENABLED"
                if env.get(flag, "false" if role == "compression" else "true").lower() not in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }:
                    config["roles"][role] = {"enabled": False}
                    continue
            names = [prefix + suffix for suffix in ("MODEL", "API_KEY", "BASE_URL")]
            values = [env.get(name, "").strip() for name in names]
            if not any(values):
                continue
            # Only the original direct SDK roles had a same-role OpenAI endpoint default.
            # Dedicated inherited roles previously borrowed URLs; require their complete identity.
            identity_size = 2 if role in {"main", "structured", "small"} else 3
            missing = [name for name, value in zip(names[:identity_size], values[:identity_size]) if not value]
            if missing:
                raise ConfigError(
                    f"{role}: incomplete legacy identity; set {', '.join(missing)} or remove all identity fields and use inheritance"
                )
            connection_id = "legacy-" + role
            if connection_id in config["connections"] or connection_id in config["models"]:
                raise ConfigError("reserved legacy configuration identifier collision")
            connection = Connection(preset="legacy", endpoint=values[2] or None, credential="env:" + names[1])
            thinking = "default"
            if role == "main" and env.get("MODEL_THINKING_MODE", "").strip():
                mode = env["MODEL_THINKING_MODE"].strip().lower()
                if mode not in {"enabled", "disabled"}:
                    raise ConfigError("MODEL_THINKING_MODE must be 'enabled' or 'disabled'")
                thinking = "on" if mode == "enabled" else "off"
            if role in {"structured", "structured_fast"} and "deepseek" in (values[0] + values[2]).lower():
                thinking = "off"
            timeout = (
                _timeout(env, "STRUCTURED_TIMEOUT_MS") if role in {"structured", "structured_fast", "memory"} else None
            )
            if role == "compression":
                timeout = _timeout(env, "CONTEXT_COMPRESSION_TIMEOUT_MS", "30000") or _timeout(
                    env, "STRUCTURED_TIMEOUT_MS"
                )
            config["connections"][connection_id] = connection.model_dump()
            config["models"][connection_id] = ModelProfile(
                connection=connection_id,
                model_id=values[0],
                parameters=Parameters(thinking=thinking, timeout=timeout),
                capabilities=legacy_capabilities(),
            ).model_dump()
            config["roles"][role] = {"model": connection_id}
        explicitly_configured = set(config["roles"])
        for role, candidates in INHERIT.items():
            if role not in config["roles"]:
                parent = next(
                    (
                        candidate
                        for candidate in candidates
                        if config["roles"].get(candidate, {}).get("enabled", True)
                        and candidate in config["roles"]
                        and (role != "memory" or candidate in explicitly_configured)
                    ),
                    None,
                )
                if parent:
                    config["roles"][role] = {"inherit": parent}
        return Configuration.model_validate(config)

    def load(self) -> ResolvedModelConfigSnapshot:
        return resolve(self.configuration(), self.environ)


def resolve(
    config: Configuration, env: Mapping[str, str] | None = None, *, file_roles: set[str] | None = None
) -> ResolvedModelConfigSnapshot:
    connections = {name: resolve_connection(connection) for name, connection in config.connections.items()}
    models = dict(config.models)
    for model in models.values():
        if model.connection not in connections:
            raise ConfigError("model references missing connection")
        validate_parameters(model, connections[model.connection])
    roles = {}

    def visit(role: str, trail: tuple[str, ...] = ()) -> RoleBinding:
        if role in trail:
            raise ConfigError("role inheritance cycle")
        if role in roles:
            return roles[role]
        binding = config.roles.get(role)
        if binding is None:
            raise ConfigError(f"{role}: required role is not configured")
        if binding.inherit:
            parent = visit(binding.inherit, (*trail, role))
            if not parent.enabled:
                raise ConfigError(f"{role}: cannot inherit disabled role")
            binding = RoleBinding(model=parent.model, fallback=binding.fallback or parent.fallback)
            if env is not None and role not in (file_roles or set()):
                profile = models[binding.model]
                timeout = None
                thinking = profile.parameters.thinking
                if role in {"memory", "structured_fast"}:
                    timeout = _timeout(env, "STRUCTURED_TIMEOUT_MS")
                if role == "compression":
                    timeout = _timeout(env, "CONTEXT_COMPRESSION_TIMEOUT_MS", "30000") or _timeout(
                        env, "STRUCTURED_TIMEOUT_MS"
                    )
                if (
                    role == "structured_fast"
                    and connections[profile.connection].preset == "legacy"
                    and "deepseek" in (profile.model_id + (connections[profile.connection].endpoint or "")).lower()
                ):
                    thinking = "off"
                if timeout or thinking != profile.parameters.thinking:
                    name = "inherited-" + role
                    models[name] = profile.model_copy(
                        update={
                            "parameters": profile.parameters.model_copy(
                                update={"timeout": timeout or profile.parameters.timeout, "thinking": thinking}
                            )
                        }
                    )
                    binding = binding.model_copy(update={"model": name})
        if not binding.enabled:
            if role not in {"compression", "video_vision"}:
                raise ConfigError(f"{role}: required role cannot be disabled")
        else:
            for name in (binding.model, *binding.fallback):
                if name not in models:
                    raise ConfigError(f"{role}: model reference is missing")
                validate_capabilities(role, models[name])
        roles[role] = binding
        return binding

    for role in config.roles:
        visit(role)
    resolved = Configuration(connections=connections, models=models, roles=roles)
    return ResolvedModelConfigSnapshot(**resolved.model_dump(), fingerprint=fingerprint(resolved))


class FileConfigRepository:
    def __init__(self, path: str | Path, *, root: Path = CONFIG_ROOT, environ: Mapping[str, str] | None = None):
        candidate = Path(path).expanduser()
        self.path = candidate if candidate.is_absolute() else root / candidate
        self.env = EnvConfigRepository(environ)

    def load(self) -> ResolvedModelConfigSnapshot:
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
            explicit = Configuration.model_validate(raw)
            # A YAML identity/inheritance graph must resolve on its own, before legacy merging.
            resolve(explicit)
            # Explicit YAML roles never receive legacy identity or option overrides.
            merged = self.env.configuration(explicit)
            return resolve(merged, self.env.environ, file_roles=set(explicit.roles))
        except (OSError, yaml.YAMLError, ValidationError):
            raise ConfigError(
                "MODEL_CONFIG_PATH cannot be loaded: check file, version and configuration fields"
            ) from None


def load_configuration() -> ResolvedModelConfigSnapshot:
    path = os.getenv("MODEL_CONFIG_PATH", "").strip()
    return FileConfigRepository(path).load() if path else EnvConfigRepository().load()

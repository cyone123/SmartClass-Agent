"""Versioned internal configuration. Never expose internal dumps to clients/logs."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Protocol = Literal["openai_chat", "anthropic_messages", "google_genai"]
Role = Literal["main", "structured", "structured_fast", "small", "memory", "compression", "video_vision"]


class ConfigError(ValueError):
    """Safe, value-free configuration diagnostic."""


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Capabilities(Schema):
    text: bool | None = None
    images: bool | None = None
    streaming: bool | None = None
    tools: bool | None = None
    tool_choice: bool | None = None
    structured: bool | None = None
    reasoning_roundtrip: bool | None = None
    context_window: int | None = Field(default=None, gt=0)
    max_output: int | None = Field(default=None, gt=0)
    source: Literal["declared", "legacy-declared", "preset"] = "declared"
    rules_version: Literal["1"] = "1"


class Parameters(Schema):
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)
    timeout: float | None = Field(default=None, gt=0)
    thinking: Literal["default", "off", "on", "adaptive"] = "default"
    thinking_budget: int | None = Field(default=None, ge=0)
    structured_method: Literal["tool_calling", "json_schema"] = "tool_calling"


class Connection(Schema):
    preset: Literal["openai", "custom", "legacy", "anthropic", "gemini"]
    protocol: Protocol = "openai_chat"
    endpoint: str | None = None
    credential: str

    @field_validator("credential")
    @classmethod
    def reference_only(cls, value: str) -> str:
        if not re.fullmatch(r"env:[A-Za-z_][A-Za-z0-9_]*", value):
            raise ConfigError("credential must be an env:NAME reference")
        return value

    @field_validator("endpoint")
    @classmethod
    def safe_endpoint(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ConfigError("endpoint must be HTTP(S) without userinfo, query or fragment")
        return value


class ProviderPreset(Schema):
    id: Literal["openai", "custom", "legacy", "anthropic", "gemini"]
    protocols: tuple[Protocol, ...]
    default_endpoint: str | None = None
    credential_fields: tuple[Literal["api_key"], ...] = ("api_key",)
    credential_source: Literal["env-reference"] = "env-reference"
    parameter_defaults: Parameters = Field(default_factory=Parameters)
    capability_rules_version: Literal["1"] = "1"

    def parameter_schema(self) -> dict:
        return Parameters.model_json_schema()


class ModelProfile(Schema):
    connection: str
    model_id: str = Field(min_length=1)
    parameters: Parameters = Field(default_factory=Parameters)
    capabilities: Capabilities = Field(default_factory=Capabilities)


class RoleBinding(Schema):
    model: str | None = None
    inherit: Role | None = None
    enabled: bool = True
    fallback: tuple[str, ...] = ()

    @model_validator(mode="after")
    def exclusive(self):
        if self.enabled and (self.model is None) == (self.inherit is None):
            raise ConfigError("role requires exactly one of model or inherit")
        if not self.enabled and (self.model or self.inherit or self.fallback):
            raise ConfigError("disabled role cannot select a model")
        return self


class Configuration(Schema):
    version: Literal[1] = 1
    connections: dict[str, Connection] = Field(default_factory=dict)
    models: dict[str, ModelProfile] = Field(default_factory=dict)
    roles: dict[Role, RoleBinding] = Field(default_factory=dict)


class ResolvedModelConfigSnapshot(Configuration):
    fingerprint: str
    rules_version: Literal["1"] = "1"

    def public_dto(self) -> dict:
        return {
            "version": self.version,
            "fingerprint": self.fingerprint,
            "rules_version": self.rules_version,
            "roles": {
                role: {"enabled": binding.enabled, "model": binding.model} for role, binding in self.roles.items()
            },
            "models": {
                name: {
                    "model_id": model.model_id,
                    "protocol": self.connections[model.connection].protocol,
                    "provider": self.connections[model.connection].preset,
                    "capabilities": model.capabilities.model_dump(),
                    "verified": False,
                }
                for name, model in self.models.items()
            },
        }


def fingerprint(config: Configuration) -> str:
    data = config.model_dump(mode="json")
    # Preserve version-1 fingerprints of snapshots persisted before native adapters.
    for model in data["models"].values():
        params = model["parameters"]
        if params.get("thinking_budget") is None:
            params.pop("thinking_budget", None)
        if params.get("structured_method") == "tool_calling":
            params.pop("structured_method", None)
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return "v1:" + hashlib.sha256(payload.encode()).hexdigest()


def restore_snapshot(data: dict) -> ResolvedModelConfigSnapshot:
    snapshot = ResolvedModelConfigSnapshot.model_validate(data)
    config = Configuration.model_validate(snapshot.model_dump(exclude={"fingerprint", "rules_version"}))
    if fingerprint(config) != snapshot.fingerprint:
        raise ConfigError("snapshot fingerprint mismatch")
    return snapshot

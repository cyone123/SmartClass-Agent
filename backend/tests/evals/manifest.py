"""Reproducibility metadata for evaluation and benchmark reports."""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.core.evaluation import EvalRunManifest
from app.core.model_access.config_repository import load_configuration
from app.core.model_access.schemas import ResolvedModelConfigSnapshot

SAFE_ENV_KEYS = (
    "CONTEXT_COMPRESSION_ENABLED",
    "CONTEXT_COMPRESSION_TRIGGER_TOKENS",
    "CONTEXT_COMPRESSION_KEEP_RECENT_TURNS",
    "WORKSPACE_EXECUTION_BACKEND",
    "OBSERVABILITY_ENABLED",
    "PROMETHEUS_ENABLED",
    "OTEL_ENABLED",
    "STRUCTURED_FALLBACK_ENABLED",
)

MODEL_ENV_ROLES = {
    "main": ("MODEL",),
    "structured": ("STRUCTURED_MODEL",),
    "fast": ("STRUCTURED_FAST_MODEL", "SMALL_MODEL"),
    "small": ("SMALL_MODEL",),
    "memory": ("MEMORY_MODEL", "STRUCTURED_FAST_MODEL", "STRUCTURED_MODEL", "SMALL_MODEL", "MODEL"),
}

ROLE_NAMES = frozenset((*MODEL_ENV_ROLES, "structured_fast", "compression", "video_vision"))
ROLE_EVIDENCE_KEYS = frozenset(
    {
        "provider",
        "protocol",
        "model",
        "thinking",
        "reasoning_effort",
        "structured_method",
        "provider_routing",
        "capability_rules_version",
        "actual_upstream",
        "fallback",
        "fallback_used",
        "attempts",
    }
)
ROUTING_EVIDENCE_KEYS = frozenset(
    {"order", "only", "ignore", "allow_fallbacks", "require_parameters", "data_collection", "sort"}
)
INTEGRATION_PACKAGES = {
    "openai_chat": ("langchain-openai", "openai"),
    "anthropic_messages": ("langchain-anthropic", "anthropic"),
    "google_genai": ("langchain-google-genai", "google-ai-generativelanguage"),
}


def dataset_fingerprint(cases_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(cases_dir.rglob("*.yaml")):
        digest.update(path.relative_to(cases_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def git_commit(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def git_source_state(repository_root: Path) -> tuple[bool, str]:
    """Fingerprint tracked changes and untracked source files without storing content."""
    try:
        status = subprocess.run(
            ["git", "-C", str(repository_root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        diff = subprocess.run(
            ["git", "-C", str(repository_root), "diff", "--binary", "HEAD"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        untracked = subprocess.run(
            ["git", "-C", str(repository_root), "ls-files", "--others", "--exclude-standard"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False, "unknown"

    digest = hashlib.sha256()
    digest.update(diff.stdout)
    for relative_name in sorted(line for line in untracked.stdout.splitlines() if line):
        relative_path = Path(relative_name)
        if relative_path.parts and relative_path.parts[0] == "storage":
            continue
        path = repository_root / relative_path
        if not path.is_file():
            continue
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return bool(status.stdout.strip()), f"sha256:{digest.hexdigest()}"


def environment_summary() -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "architecture": platform.machine(),
        "config": {key: os.environ[key] for key in SAFE_ENV_KEYS if key in os.environ},
    }


def sanitize_model_summary(model: dict[str, Any] | None) -> dict[str, Any]:
    if not model:
        return {}
    allowed = (
        "provider",
        "model",
        "models",
        "temperature",
        "top_p",
        "max_tokens",
        "judge_model",
        "configuration_version",
        "capability_rules_version",
        "integration_versions",
        "roles",
    )
    sanitized = {key: model[key] for key in allowed if model.get(key) is not None}
    if isinstance(sanitized.get("models"), dict):
        sanitized["models"] = {
            str(role): str(name) for role, name in sanitized["models"].items() if role in ROLE_NAMES and name
        }
    if isinstance(sanitized.get("integration_versions"), dict):
        sanitized["integration_versions"] = {
            str(name): str(version)
            for name, version in sanitized["integration_versions"].items()
            if isinstance(name, str) and isinstance(version, str)
        }
    if isinstance(sanitized.get("roles"), dict):
        roles = {}
        for role, value in sanitized["roles"].items():
            if role not in ROLE_NAMES or not isinstance(value, dict):
                continue
            safe = {key: value[key] for key in ROLE_EVIDENCE_KEYS if value.get(key) is not None}
            routing = safe.get("provider_routing")
            if isinstance(routing, dict):
                safe["provider_routing"] = {
                    key: routing[key] for key in ROUTING_EVIDENCE_KEYS if routing.get(key) not in (None, [], ())
                }
            elif routing is not None:
                safe.pop("provider_routing", None)
            for collection_key in ("fallback", "attempts"):
                collection = safe.get(collection_key)
                if isinstance(collection, list):
                    safe[collection_key] = [
                        {key: item[key] for key in ("provider", "protocol", "model") if item.get(key) is not None}
                        for item in collection
                        if isinstance(item, dict)
                    ]
                elif collection is not None:
                    safe.pop(collection_key, None)
            roles[str(role)] = safe
        sanitized["roles"] = roles
    return sanitized


def _package_versions(protocols: set[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for protocol in sorted(protocols):
        for package in INTEGRATION_PACKAGES.get(protocol, ()):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = "unavailable"
    return versions


def model_summary_from_snapshot(
    snapshot: ResolvedModelConfigSnapshot,
    invocation_metadata: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build allowlisted evidence from resolved identities, never URLs or credentials."""
    invocation_metadata = invocation_metadata or {}
    roles: dict[str, dict[str, Any]] = {}
    protocols: set[str] = set()
    for role, binding in snapshot.roles.items():
        if not binding.enabled or not binding.model:
            continue
        profile = snapshot.models[binding.model]
        connection = snapshot.connections[profile.connection]
        protocols.add(connection.protocol)
        call = invocation_metadata.get(role) or {}
        fallback = []
        for fallback_name in binding.fallback:
            fallback_profile = snapshot.models[fallback_name]
            fallback_connection = snapshot.connections[fallback_profile.connection]
            fallback.append(
                {
                    "provider": fallback_connection.preset,
                    "protocol": fallback_connection.protocol,
                    "model": fallback_profile.model_id,
                }
            )
        roles[role] = {
            "provider": connection.preset,
            "protocol": connection.protocol,
            "model": profile.model_id,
            "thinking": profile.parameters.thinking,
            "reasoning_effort": profile.parameters.reasoning_effort,
            "structured_method": profile.parameters.structured_method,
            "provider_routing": (
                profile.parameters.provider_routing.model_dump(mode="json")
                if profile.parameters.provider_routing
                else (
                    {"allow_fallbacks": True, "require_parameters": True} if connection.preset == "openrouter" else None
                )
            ),
            "capability_rules_version": profile.capabilities.rules_version,
            "actual_upstream": call.get("smartclass_actual_upstream") or "unknown",
            "fallback": fallback,
            "fallback_used": bool(call.get("smartclass_fallback_used", False)),
            "attempts": call.get("smartclass_attempts") or [],
        }
    main = roles.get("main", {})
    return sanitize_model_summary(
        {
            "provider": main.get("provider", "unknown"),
            "model": main.get("model"),
            "models": {role: item["model"] for role, item in roles.items()},
            "configuration_version": snapshot.fingerprint,
            "capability_rules_version": snapshot.rules_version,
            "integration_versions": _package_versions(protocols),
            "roles": roles,
        }
    )


def model_summary_from_environment() -> dict[str, Any]:
    """Resolve the same configuration graph used by runtime; never infer provider from URLs."""
    return model_summary_from_snapshot(load_configuration())


def build_run_manifest(
    *,
    cases_dir: Path,
    repository_root: Path | None = None,
    model: dict[str, Any] | None = None,
    commands: list[str] | None = None,
) -> EvalRunManifest:
    backend_root = repository_root or Path(__file__).resolve().parents[2]
    repository_dirty, source_fingerprint = git_source_state(backend_root)
    return EvalRunManifest(
        dataset_fingerprint=dataset_fingerprint(cases_dir),
        git_commit=git_commit(backend_root),
        repository_dirty=repository_dirty,
        source_fingerprint=source_fingerprint,
        environment=environment_summary(),
        model=sanitize_model_summary(model) if model is not None else model_summary_from_environment(),
        commands=list(commands or []),
    )

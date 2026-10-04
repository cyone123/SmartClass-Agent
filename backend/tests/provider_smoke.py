"""Explicit live provider smoke runner, separate from the 24-case business eval suite.

Run from backend/:
  python -m tests.provider_smoke --providers openrouter deepseek zhipu --output <path>

Each provider requires ``<PREFIX>_API_KEY`` and ``<PREFIX>_MODEL``. Optional
``<PREFIX>_SMOKE_CAPABILITIES`` declares comma-separated structured, thinking,
and/or vision checks for that exact model. Missing access is unverified and the
gate exits non-zero; it is never converted into a pass.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from dotenv import dotenv_values
from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import BaseModel

from app.core.model_access.config_repository import resolve
from app.core.model_access.factory import ModelFactory
from app.core.model_access.messages import display_text
from app.core.model_access.schemas import Configuration
from app.core.model_access.secrets import SecretResolver

PROVIDERS = {
    "openrouter": {"prefix": "OPENROUTER", "declared": ()},
    "deepseek": {"prefix": "DEEPSEEK", "declared": ("structured", "thinking")},
    "zhipu": {"prefix": "ZHIPU", "declared": ("structured", "thinking")},
}
MANDATORY = ("text", "stream", "tools")
OPTIONAL = {"structured", "thinking", "vision"}


class SmokeAnswer(BaseModel):
    value: int


@dataclass(frozen=True)
class SmokeResult:
    provider: str
    model: str
    protocol: str
    capability: str
    status: str
    reason: str | None = None
    actual_upstream: str = "unknown"


def _package_versions() -> dict[str, str]:
    result = {}
    for package in ("langchain", "langchain-core", "langchain-openai", "openai"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "unavailable"
    return result


def _safe_reason(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    if "auth" in name or "permission" in name:
        return "authentication_or_permission"
    if "timeout" in name:
        return "timeout"
    if "rate" in name:
        return "rate_limit"
    return "provider_or_contract_error"


def _environment() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    return {key: str(value) for key, value in {**dotenv_values(root / ".env"), **os.environ}.items() if value}


def _capabilities(provider: str, env: dict[str, str], prefix: str) -> tuple[str, ...]:
    declared = {item.strip().lower() for item in env.get(prefix + "_SMOKE_CAPABILITIES", "").split(",") if item.strip()}
    unknown = declared - OPTIONAL
    if unknown:
        raise ValueError("unsupported smoke capability declaration")
    optional = {*PROVIDERS[provider]["declared"], *declared}
    return (*MANDATORY, *sorted(optional))


def _snapshot(provider: str, env: dict[str, str], capability: str):
    info = PROVIDERS[provider]
    prefix = info["prefix"]
    endpoint = env.get(prefix + "_BASE_URL")
    parameters = {"max_tokens": 1024, "timeout": 60}
    tool_choice = True
    reasoning_roundtrip = False
    if capability == "thinking":
        parameters["thinking"] = "on"
        reasoning_roundtrip = provider in {"deepseek", "zhipu"}
        if provider == "deepseek":
            parameters["reasoning_effort"] = env.get(prefix + "_REASONING_EFFORT", "high")
            tool_choice = False
    if provider == "openrouter":
        parameters["provider_routing"] = {
            "allow_fallbacks": env.get("OPENROUTER_ALLOW_FALLBACKS", "true").lower() in {"1", "true", "yes"},
            "require_parameters": True,
        }
    raw = {
        "connections": {
            "live": {
                "preset": provider,
                "protocol": "openai_chat",
                "credential": f"env:{prefix}_API_KEY",
                **({"endpoint": endpoint} if endpoint else {}),
            }
        },
        "models": {
            "live": {
                "connection": "live",
                "model_id": env[prefix + "_MODEL"],
                "parameters": parameters,
                "capabilities": {
                    "text": True,
                    "streaming": True,
                    "tools": True,
                    "tool_choice": tool_choice,
                    "structured": capability == "structured",
                    "images": capability == "vision",
                    "reasoning_roundtrip": reasoning_roundtrip,
                    "source": "declared",
                    "verification": "declared",
                },
            }
        },
        "roles": {"main": {"model": "live"}},
    }
    return resolve(Configuration.model_validate(raw))


async def _check(model, capability: str):
    prompt = [HumanMessage("Reply with one short greeting.")]
    if capability == "stream":
        chunks = [chunk async for chunk in model.astream(prompt)]
        if not "".join(display_text(chunk) for chunk in chunks).strip():
            raise AssertionError("empty stream")
        return chunks[-1] if chunks else None
    if capability == "tools":
        schema = {
            "name": "smoke_add",
            "description": "Add two integers",
            "parameters": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        }
        request = [HumanMessage("Use smoke_add to add 2 and 3.")]
        reply = await model.bind_tools([schema]).ainvoke(request)
        if len(reply.tool_calls) != 1:
            raise AssertionError("tool call missing")
        call = reply.tool_calls[0]
        result = await model.bind_tools([schema]).ainvoke([*request, reply, ToolMessage("5", tool_call_id=call["id"])])
        if not display_text(result).strip():
            raise AssertionError("tool continuation missing")
        return result
    if capability == "structured":
        answer = await model.with_structured_output(SmokeAnswer).ainvoke("Return value 7.")
        if answer.value != 7:
            raise AssertionError("structured value mismatch")
        return None
    if capability == "vision":
        png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
        reply = await model.ainvoke(
            [
                HumanMessage(
                    content=[
                        {"type": "text", "text": "Describe this image briefly."},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png}},
                    ]
                )
            ]
        )
    else:
        reply = await model.ainvoke(prompt)
    if not display_text(reply).strip():
        raise AssertionError("empty response")
    return reply


async def run_provider(provider: str, env: dict[str, str]) -> list[SmokeResult]:
    prefix = PROVIDERS[provider]["prefix"]
    model_id = env.get(prefix + "_MODEL", "unconfigured")
    capabilities = _capabilities(provider, env, prefix)
    if not env.get(prefix + "_API_KEY") or model_id == "unconfigured":
        return [
            SmokeResult(provider, model_id, "openai_chat", capability, "unverified", "credential_or_model_missing")
            for capability in capabilities
        ]
    results = []
    for capability in capabilities:
        factory = ModelFactory(SecretResolver(env))
        try:
            model = factory.get("main", streaming=capability == "stream", snapshot=_snapshot(provider, env, capability))
            reply = await _check(model, capability)
            upstream = getattr(reply, "response_metadata", {}).get("smartclass_actual_upstream", "unknown")
            results.append(
                SmokeResult(provider, model_id, "openai_chat", capability, "passed", actual_upstream=upstream)
            )
        except Exception as exc:
            results.append(SmokeResult(provider, model_id, "openai_chat", capability, "failed", _safe_reason(exc)))
        finally:
            await factory.close()
    return results


async def run(providers: list[str], output: Path | None = None) -> tuple[dict, bool]:
    env = _environment()
    results = []
    for provider in providers:
        results.extend(await run_provider(provider, env))
    report = {
        "schema": "smartclass-provider-smoke-v1",
        "run_mode": "live-provider-smoke",
        "generated_at": datetime.now(UTC).isoformat(),
        "dependencies": _package_versions(),
        "results": [asdict(result) for result in results],
        "summary": {
            status: sum(result.status == status for result in results) for status in ("passed", "failed", "unverified")
        },
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, bool(results) and all(result.status == "passed" for result in results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run explicit live provider compatibility smokes.")
    parser.add_argument("--providers", nargs="+", choices=tuple(PROVIDERS), default=list(PROVIDERS))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report, passed = asyncio.run(run(args.providers, args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

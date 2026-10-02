"""Explicit live checks: pytest -m model_eval tests/test_native_provider_smoke.py.

No models are guessed and no credentials are borrowed from legacy OpenAI roles.
Missing access is unverified (skip), never evidence of provider support.
"""

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import BaseModel

from app.core.model_access.config_repository import resolve
from app.core.model_access.factory import ModelFactory
from app.core.model_access.messages import display_text
from app.core.model_access.schemas import Configuration
from app.core.model_access.secrets import SecretResolver

pytestmark = [pytest.mark.model_eval, pytest.mark.asyncio]


class SmokeAnswer(BaseModel):
    value: int


@pytest.mark.parametrize(
    "provider,protocol,prefix",
    [
        ("anthropic", "anthropic_messages", "ANTHROPIC"),
        ("gemini", "google_genai", "GEMINI"),
    ],
)
@pytest.mark.parametrize("capability", ["chat", "stream", "tools", "structured", "vision"])
async def test_native_smoke(provider, protocol, prefix, capability):
    env = {**dotenv_values(Path(__file__).resolve().parents[2] / ".env"), **os.environ}
    if not env.get(f"{prefix}_API_KEY") or not env.get(f"{prefix}_MODEL"):
        pytest.skip("UNVERIFIED: native credential or model selection missing")
    snapshot = resolve(
        Configuration.model_validate(
            {
                "connections": {
                    "live": {"preset": provider, "protocol": protocol, "credential": f"env:{prefix}_API_KEY"}
                },
                "models": {
                    "live": {
                        "connection": "live",
                        "model_id": env[f"{prefix}_MODEL"],
                        "parameters": {"max_tokens": 1024, "timeout": 45},
                        "capabilities": {
                            "text": True,
                            "streaming": True,
                            "tools": True,
                            "tool_choice": True,
                            "images": True,
                        },
                    }
                },
                "roles": {"main": {"model": "live"}},
            }
        )
    )
    factory = ModelFactory(SecretResolver(env))
    try:
        model = factory.get("main", snapshot=snapshot)
        prompt = [HumanMessage("Reply with one short greeting.")]
        if capability == "stream":
            chunks = [chunk async for chunk in model.astream(prompt)]
            assert "".join(display_text(c) for c in chunks).strip()
        elif capability == "tools":
            schema = {
                "name": "smoke_add",
                "description": "Add two integers",
                "parameters": {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
            }
            prompt = [HumanMessage("Use smoke_add to add 2 and 3.")]
            reply = await model.bind_tools([schema], tool_choice="smoke_add").ainvoke(prompt)
            assert len(reply.tool_calls) == 1
            call = reply.tool_calls[0]
            assert call["name"] == "smoke_add" and call["args"] == {"a": 2, "b": 3}
            result = await model.ainvoke([*prompt, reply, ToolMessage("5", tool_call_id=call["id"])])
            assert "5" in display_text(result)
        elif capability == "structured":
            answer = await model.with_structured_output(SmokeAnswer).ainvoke("Return value 7.")
            assert answer.value == 7
        elif capability == "vision":
            png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
            result = await model.ainvoke(
                [
                    HumanMessage(
                        content=[
                            {"type": "text", "text": "Describe this image briefly."},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png}},
                        ]
                    )
                ]
            )
            assert display_text(result).strip()
        else:
            assert display_text(await model.ainvoke(prompt)).strip()
    finally:
        await factory.close()

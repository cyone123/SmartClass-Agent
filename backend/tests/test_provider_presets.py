"""Offline provider-preset contracts; these are not live compatibility evidence."""

import json

import httpx
import pytest
from langchain_core.messages import HumanMessage, ToolMessage, message_chunk_to_message

from app.core.model_access.config_repository import resolve
from app.core.model_access.factory import ModelFactory
from app.core.model_access.messages import display_text
from app.core.model_access.registry import PRESETS, public_preset_catalog
from app.core.model_access.schemas import ConfigError, Configuration
from app.core.model_access.secrets import SecretResolver

TOOL = {
    "name": "lookup",
    "description": "Look up a topic",
    "parameters": {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
        "required": ["topic"],
    },
}


def provider_config(preset, *, model="fixture-model", parameters=None, capabilities=None, endpoint=None):
    thinking_on = (parameters or {}).get("thinking") == "on"
    return resolve(
        Configuration.model_validate(
            {
                "connections": {
                    "provider": {
                        "preset": preset,
                        "protocol": "openai_chat",
                        "credential": "env:PROVIDER_KEY",
                        **({"endpoint": endpoint} if endpoint else {}),
                    }
                },
                "models": {
                    "provider": {
                        "connection": "provider",
                        "model_id": model,
                        "parameters": parameters or {},
                        "capabilities": capabilities
                        or {
                            "text": True,
                            "streaming": True,
                            "tools": True,
                            "tool_choice": not (preset == "deepseek" and thinking_on),
                            "structured": True,
                            "reasoning_roundtrip": preset in {"deepseek", "zhipu"},
                            "source": "preset",
                            "verification": "declared",
                        },
                    }
                },
                "roles": {"main": {"model": "provider"}},
            }
        )
    )


@pytest.fixture
def model_harness(monkeypatch):
    factories = []

    def create(snapshot, responses):
        requests = []

        def respond(request):
            requests.append(request)
            body = responses[min(len(requests) - 1, len(responses) - 1)]
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(respond)
        sync = httpx.Client(transport=transport)
        async_client = httpx.AsyncClient(transport=transport)
        factory = ModelFactory(SecretResolver({"PROVIDER_KEY": "offline-secret"}))
        monkeypatch.setattr(factory, "_new_clients", lambda: (sync, async_client))
        factories.append(factory)
        return factory.get("main", snapshot=snapshot), requests

    yield create


def completion(*, reasoning=None, provider=None, tool=True):
    message = {"role": "assistant", "content": "Visible"}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    if tool:
        message["tool_calls"] = [
            {
                "id": "call-one",
                "type": "function",
                "function": {"name": "lookup", "arguments": '{"topic":"math"}'},
            }
        ]
    return {
        "id": "offline",
        "object": "chat.completion",
        "created": 1,
        "model": "fixture-model",
        "provider": provider,
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if tool else "stop"}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("model_id", ["anthropic/claude-test", "deepseek/deepseek-test"])
async def test_openrouter_keeps_selected_protocol_and_routing(model_harness, model_id):
    snapshot = provider_config(
        "openrouter",
        model=model_id,
        parameters={
            "thinking": "on",
            "provider_routing": {"order": ["Anthropic", "Google"], "allow_fallbacks": False},
        },
    )
    model, requests = model_harness(snapshot, [completion(provider="Anthropic")])
    reply = await model.bind_tools([TOOL]).ainvoke([HumanMessage("q")])
    payload = json.loads(requests[0].content)
    assert model.metadata["smartclass_protocol"] == "openai_chat"
    assert payload["provider"] == {
        "order": ["Anthropic", "Google"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert payload["reasoning"] == {"effort": "high"}
    assert reply.response_metadata["smartclass_actual_upstream"] == "Anthropic"


@pytest.mark.asyncio
async def test_openrouter_unknown_upstream_is_not_inferred(model_harness):
    snapshot = provider_config("openrouter", model="anthropic/claude-test")
    model, _ = model_harness(snapshot, [completion(provider=None)])
    reply = await model.ainvoke([HumanMessage("q")])
    assert reply.response_metadata["smartclass_actual_upstream"] == "unknown"


@pytest.mark.asyncio
async def test_deepseek_reasoning_content_survives_tool_roundtrip(model_harness):
    snapshot = provider_config(
        "deepseek",
        model="deepseek-flash",
        parameters={"thinking": "on", "reasoning_effort": "high"},
    )
    model, requests = model_harness(
        snapshot,
        [completion(reasoning="opaque-reasoning"), completion(reasoning="next", tool=False)],
    )
    reply = await model.bind_tools([TOOL]).ainvoke([HumanMessage("q")])
    assert display_text(reply) == "Visible"
    assert reply.additional_kwargs["reasoning_content"] == "opaque-reasoning"
    await model.bind_tools([TOOL]).ainvoke(
        [HumanMessage("q"), reply, ToolMessage("42", tool_call_id=reply.tool_calls[0]["id"])]
    )
    payload = json.loads(requests[-1].content)
    assistant = next(message for message in payload["messages"] if message["role"] == "assistant")
    assert assistant["reasoning_content"] == "opaque-reasoning"
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_deepseek_stream_preserves_reasoning_delta(monkeypatch):
    snapshot = provider_config(
        "deepseek",
        model="deepseek-flash",
        parameters={"thinking": "on"},
    )
    events = [
        {
            "id": "offline",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "deepseek-flash",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "", "reasoning_content": "opaque"},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "offline",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "deepseek-flash",
            "choices": [{"index": 0, "delta": {"content": "Visible"}, "finish_reason": "stop"}],
        },
    ]
    body = "".join("data: " + json.dumps(event) + "\n\n" for event in events) + "data: [DONE]\n\n"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
    )
    sync = httpx.Client(transport=transport)
    async_client = httpx.AsyncClient(transport=transport)
    factory = ModelFactory(SecretResolver({"PROVIDER_KEY": "offline-secret"}))
    monkeypatch.setattr(factory, "_new_clients", lambda: (sync, async_client))
    model = factory.get("main", snapshot=snapshot, streaming=True)
    chunks = [chunk async for chunk in model.astream([HumanMessage("q")])]
    merged = message_chunk_to_message(sum(chunks[1:], chunks[0]))
    assert display_text(merged) == "Visible"
    assert merged.additional_kwargs["reasoning_content"] == "opaque"


def test_deepseek_thinking_rules_and_legacy_disable_policy():
    with pytest.raises(ConfigError, match="temperature"):
        provider_config("deepseek", parameters={"thinking": "on", "temperature": 0.2})
    with pytest.raises(ConfigError, match="forced tool"):
        provider_config(
            "deepseek",
            parameters={"thinking": "on"},
            capabilities={
                "text": True,
                "streaming": True,
                "tools": True,
                "tool_choice": True,
                "reasoning_roundtrip": True,
            },
        )


@pytest.mark.asyncio
async def test_zhipu_domestic_default_custom_model_and_thinking(model_harness):
    snapshot = provider_config("zhipu", model="glm-custom-id", parameters={"thinking": "on"})
    model, requests = model_harness(snapshot, [completion(reasoning="opaque", tool=False)])
    reply = await model.ainvoke([HumanMessage("q")])
    assert snapshot.connections["provider"].endpoint == "https://open.bigmodel.cn/api/paas/v4/"
    assert str(requests[0].url).startswith("https://open.bigmodel.cn/api/paas/v4/")
    assert json.loads(requests[0].content)["thinking"] == {"type": "enabled"}
    assert reply.additional_kwargs["reasoning_content"] == "opaque"


def test_all_presets_publish_safe_schema_and_support_multiple_connections():
    expected = {"openai", "custom", "legacy", "anthropic", "gemini", "openrouter", "deepseek", "zhipu"}
    assert set(PRESETS) == expected
    serialized = json.dumps(public_preset_catalog())
    assert {entry["id"] for entry in public_preset_catalog()} == expected
    assert "https://" not in serialized and "env:" not in serialized and "secret" not in serialized.lower()
    config = Configuration.model_validate(
        {
            "connections": {
                "first": {"preset": "openrouter", "credential": "env:FIRST_KEY"},
                "second": {"preset": "openrouter", "credential": "env:SECOND_KEY"},
            },
            "models": {
                "first": {"connection": "first", "model_id": "vendor/model", "capabilities": {"text": True}},
                "second": {"connection": "second", "model_id": "vendor/model", "capabilities": {"text": True}},
            },
            "roles": {"small": {"model": "first"}, "compression": {"model": "second"}},
        }
    )
    snapshot = resolve(config)
    assert snapshot.models["first"].connection != snapshot.models["second"].connection


def test_provider_specific_parameters_and_adapter_limits_fail_closed():
    with pytest.raises(ConfigError, match="only supported by the OpenRouter"):
        provider_config("zhipu", parameters={"provider_routing": {"require_parameters": True}})
    with pytest.raises(ConfigError, match="selected provider preset"):
        provider_config("zhipu", parameters={"reasoning_effort": "high"})
    custom = Configuration.model_validate(
        {
            "connections": {
                "custom": {
                    "preset": "custom",
                    "protocol": "openai_chat",
                    "endpoint": "https://offline.invalid/v1",
                    "credential": "env:CUSTOM_KEY",
                }
            },
            "models": {
                "custom": {
                    "connection": "custom",
                    "model_id": "anything",
                    "capabilities": {"text": True, "reasoning_roundtrip": True},
                }
            },
            "roles": {"small": {"model": "custom"}},
        }
    )
    with pytest.raises(ConfigError, match="unsupported by this OpenAI adapter"):
        resolve(custom)

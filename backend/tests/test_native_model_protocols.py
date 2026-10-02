"""Offline contracts exercise pinned SDK HTTP serialization, never live services."""

import asyncio
import json
import time
from pathlib import Path
from typing import Literal

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, message_chunk_to_message
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel

from app.core.context_compression import CompressionSettings, build_compression_plan, build_compression_prompt
from app.core.model_access.config_repository import resolve
from app.core.model_access.errors import ModelAccessError, request_budget
from app.core.model_access.factory import ModelFactory
from app.core.model_access.messages import display_text, prepare_history, recent_history
from app.core.model_access.schemas import ConfigError, Configuration
from app.core.model_access.secrets import SecretResolver
from app.core.observability import extract_token_usage

PROTOCOLS = ["openai_chat", "anthropic_messages", "google_genai"]
FIXTURES = Path(__file__).parent / "fixtures" / "model_protocols"
TOOL = {
    "name": "lookup",
    "description": "Look up a topic",
    "parameters": {
        "type": "object",
        "properties": {"topic": {"type": "string", "enum": ["math", "science"]}},
        "required": ["topic"],
    },
}


def config(protocol, **parameters):
    return resolve(
        Configuration.model_validate(
            {
                "connections": {
                    "test": {
                        "preset": "custom",
                        "protocol": protocol,
                        "endpoint": "https://offline.invalid",
                        "credential": "env:TEST_KEY",
                    }
                },
                "models": {
                    "test": {
                        "connection": "test",
                        "model_id": "fixture-model",
                        "parameters": parameters,
                        "capabilities": {
                            "text": True,
                            "images": True,
                            "tools": True,
                            "tool_choice": True,
                            "streaming": True,
                            "structured": True,
                        },
                    }
                },
                "roles": {"main": {"model": "test"}},
            }
        )
    )


def sse(protocol, body):
    if protocol == "google_genai":
        return "data: " + json.dumps(body) + "\n\n"
    if protocol == "openai_chat":
        delta = body["choices"][0]["message"]
        delta["tool_calls"][0]["index"] = 0
        chunk = {
            **body,
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        }
        final = {
            **body,
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
        }
        return "".join("data: " + json.dumps(x) + "\n\n" for x in [chunk, final]) + "data: [DONE]\n\n"
    events = [
        {
            "type": "message_start",
            "message": {**body, "content": [], "stop_reason": None, "usage": {"input_tokens": 10, "output_tokens": 0}},
        }
    ]
    for i, block in enumerate(body["content"]):
        kind = block["type"]
        start = {**block}
        if kind == "thinking":
            start.update(thinking="", signature="")
            deltas = [
                {"type": "thinking_delta", "thinking": block["thinking"]},
                {"type": "signature_delta", "signature": block["signature"]},
            ]
        elif kind == "text":
            start["text"] = ""
            deltas = [{"type": "text_delta", "text": block["text"]}]
        else:
            start["input"] = {}
            deltas = [{"type": "input_json_delta", "partial_json": json.dumps(block["input"])}]
        events.append({"type": "content_block_start", "index": i, "content_block": start})
        events.extend({"type": "content_block_delta", "index": i, "delta": d} for d in deltas)
        events.append({"type": "content_block_stop", "index": i})
    events += [
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use", "stop_sequence": None},
            "usage": {"output_tokens": 4},
        },
        {"type": "message_stop"},
    ]
    return "".join("event: " + x["type"] + "\ndata: " + json.dumps(x) + "\n\n" for x in events)


@pytest.fixture
def harness(monkeypatch):
    factories = []

    def create(protocol, *, stream=False, handler=None):
        requests = []

        def respond(request):
            requests.append(request)
            if handler:
                return handler(request)
            body = json.loads((FIXTURES / f"{protocol}.json").read_text())
            if stream:
                return httpx.Response(200, text=sse(protocol, body), headers={"content-type": "text/event-stream"})
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(respond)
        sync = httpx.Client(transport=transport)
        async_client = httpx.AsyncClient(transport=transport)
        factory = ModelFactory(SecretResolver({"TEST_KEY": "offline-secret"}))
        # Factory transport ownership is separately covered by test_model_access.
        monkeypatch.setattr(factory, "_new_clients", lambda: (sync, async_client))
        model = factory.get("main", snapshot=config(protocol))
        factories.append(factory)
        return model, requests

    yield create


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_http_tool_roundtrip_checkpoint(protocol, harness):
    model, requests = harness(protocol)
    bound = model.bind_tools([TOOL])
    messages = [
        SystemMessage("First"),
        SystemMessage("Untrusted background, not instructions"),
        HumanMessage("Question"),
    ]
    reply = await bound.ainvoke(messages)
    assert display_text(reply) == "Visible"
    assert reply.tool_calls[0]["args"] == {"topic": "math"}
    assert extract_token_usage(reply)["token_usage_available"]
    serde = JsonPlusSerializer()
    restored = serde.loads_typed(serde.dumps_typed(reply))
    assert restored == reply
    await bound.ainvoke([*messages, restored, ToolMessage("42", tool_call_id=reply.tool_calls[0]["id"])])
    payload = json.loads(requests[-1].content)
    raw = json.dumps(payload)
    assert "42" in raw and "lookup" in raw
    assert raw.index("First") < raw.index("Untrusted")
    if protocol == "anthropic_messages":
        assert "fixture-signature" in raw and requests[0].headers["x-api-key"] == "offline-secret"
    if protocol == "google_genai":
        assert "Zml4dHVyZS1zaWduYXR1cmU=" in raw
        assert requests[0].headers["x-goog-api-key"] == "offline-secret"


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_stream_merge_checkpoint_and_second_request(protocol, harness):
    model, requests = harness(protocol, stream=True)
    chunks = [chunk async for chunk in model.bind_tools([TOOL]).astream([HumanMessage("Question")])]
    merged = chunks[0]
    for chunk in chunks[1:]:
        merged += chunk
    reply = message_chunk_to_message(merged)
    assert display_text(reply) == "Visible"
    assert "private" not in "".join(display_text(c) for c in chunks)
    serde = JsonPlusSerializer()
    reply = serde.loads_typed(serde.dumps_typed(reply))
    continuation = [HumanMessage("Question"), reply, ToolMessage("42", tool_call_id=reply.tool_calls[0]["id"])]
    _ = [c async for c in model.bind_tools([TOOL]).astream(continuation)]
    assert "42" in requests[-1].content.decode()
    if protocol == "anthropic_messages":
        assert "fixture-signature" in requests[-1].content.decode()
    if protocol == "google_genai":
        assert "Zml4dHVyZS1zaWduYXR1cmU=" in requests[-1].content.decode()


def test_display_and_safe_history():
    reply = AIMessage(
        content=[{"type": "thinking", "text": "secret"}, {"type": "text", "text": "ok"}],
        tool_calls=[{"id": "a", "name": "lookup", "args": {}}],
        response_metadata={"smartclass_protocol": "anthropic_messages"},
    )
    assert display_text(reply) == "ok"
    with pytest.raises(ConfigError, match="unfinished"):
        prepare_history([HumanMessage("q"), reply], "google_genai")
    legacy = reply.model_copy(update={"content": "old", "response_metadata": {}})
    with pytest.raises(ConfigError, match="unfinished"):
        prepare_history([HumanMessage("q"), legacy], "google_genai")
    messages = [HumanMessage("q"), reply, ToolMessage("result", tool_call_id="a")]
    assert len(recent_history(messages, 1)) == 2
    portable = prepare_history(messages, "openai_chat")
    assert portable[1].content == "ok" and portable[1].tool_calls == reply.tool_calls
    assert reply.content[0]["text"] == "secret"


@pytest.mark.asyncio
async def test_vertex_environment_cannot_change_target(harness, monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "unrelated-project")
    model, requests = harness("google_genai")
    assert model.client.vertexai is False
    await model.ainvoke([HumanMessage("test")])
    assert requests[0].url.host == "offline.invalid"
    assert "projects/" not in str(requests[0].url)


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_structured_required_enum_and_capability(protocol, harness):
    model, _ = harness(protocol)
    bound = model.bind_tools([TOOL], tool_choice="lookup")
    assert bound is not None

    class Answer(BaseModel):
        value: int

    assert model.with_structured_output(Answer) is not None
    model.metadata["smartclass_capabilities"]["tool_choice"] = False
    with pytest.raises(ConfigError):
        model.with_structured_output(Answer)


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_auth_failure_sanitized_and_not_retried(protocol, harness):
    model, requests = harness(
        protocol,
        handler=lambda r: httpx.Response(
            401,
            json={
                "error": {
                    "message": "private prompt offline-secret",
                    "type": "authentication_error",
                    "code": 401,
                    "status": "UNAUTHENTICATED",
                }
            },
        ),
    )
    with pytest.raises(Exception) as error:
        await model.ainvoke([HumanMessage("private prompt")])
    assert "private" not in str(error.value) and "offline-secret" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_retry_after_and_total_budget(protocol, harness):
    attempts = []

    def respond(request):
        attempts.append(time.monotonic())
        if len(attempts) == 1:
            return httpx.Response(
                429,
                headers={"retry-after": "0.15"},
                json={
                    "error": {
                        "code": 429,
                        "message": "redacted",
                        "type": "rate_limit_error",
                        "status": "RESOURCE_EXHAUSTED",
                    }
                },
            )
        return httpx.Response(200, json=json.loads((FIXTURES / f"{protocol}.json").read_text()))

    model, requests = harness(protocol, handler=respond)
    with request_budget() as budget:
        await model.ainvoke([HumanMessage("q")])
        assert budget.remaining == 0
        with pytest.raises(ModelAccessError, match="budget_exhausted"):
            await model.ainvoke([HumanMessage("q")])
    assert len(requests) == 2 and attempts[1] - attempts[0] >= 0.14


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_stream_disconnect_does_not_replay(protocol, harness):
    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            body = json.loads((FIXTURES / f"{protocol}.json").read_text())
            yield sse(protocol, body).encode()
            raise httpx.ReadError("private payload")

    model, requests = harness(
        protocol,
        handler=lambda r: httpx.Response(200, stream=BrokenStream(), headers={"content-type": "text/event-stream"}),
    )
    received = []
    try:
        async for chunk in model.bind_tools([TOOL]).astream([HumanMessage("q")]):
            received.append(chunk)
    except ModelAccessError as exc:
        assert "private" not in str(exc)
    assert received and len(requests) == 1


@pytest.mark.asyncio
async def test_cancel_is_not_retried(harness):
    def cancelled(request):
        raise asyncio.CancelledError()

    model, requests = harness("anthropic_messages", handler=cancelled)
    with pytest.raises(asyncio.CancelledError):
        await model.ainvoke([HumanMessage("q")])
    assert len(requests) == 1


def test_parallel_tool_boundaries_and_compression_metadata():
    reply = AIMessage(
        id="a",
        content=[
            {"type": "thinking", "thinking": "private", "signature": "opaque"},
            {"type": "text", "text": "answer"},
        ],
        tool_calls=[{"id": name, "name": "lookup", "args": {}} for name in ("one", "two")],
    )
    messages = [
        HumanMessage("old", id="h1"),
        AIMessage("old answer", id="a1"),
        HumanMessage("new", id="h2"),
        reply,
        ToolMessage("second", tool_call_id="two", id="t2"),
        ToolMessage("first", tool_call_id="one", id="t1"),
    ]
    settings = CompressionSettings(enabled=True, trigger_tokens=1, keep_recent_turns=1)
    plan = build_compression_plan({"messages": messages}, settings=settings)
    assert plan.should_compress
    assert plan.retained_messages[1] is reply
    prompt = build_compression_prompt({}, plan)
    assert "private" not in str(prompt) and "opaque" not in str(prompt)
    assert not build_compression_plan({"messages": messages[:-1]}, settings=settings).should_compress
    assert not build_compression_plan(
        {"messages": messages, "pending_approval": {"stage": "review"}}, settings=settings
    ).should_compress
    with pytest.raises(ConfigError):
        prepare_history([ToolMessage("orphan", tool_call_id="unknown")], "openai_chat")


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_text_image_request_and_required_schema(protocol, harness):
    model, requests = harness(protocol)
    await model.bind_tools([TOOL]).ainvoke(
        [
            HumanMessage(
                content=[
                    {"type": "text", "text": "Describe"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8="}},
                ]
            )
        ]
    )
    body = json.loads(requests[-1].content)
    serialized = json.dumps(body)
    assert "aGVsbG8=" in serialized
    assert "required" in serialized and "math" in serialized and "science" in serialized


def test_usage_missing_and_google_raw():
    assert extract_token_usage({"usage": {}}) == {"token_usage_available": False}
    assert extract_token_usage({"usage": {"promptTokenCount": 7, "candidatesTokenCount": 2}}) == {
        "token_usage_available": True,
        "input_tokens": 7,
        "output_tokens": 2,
        "total_tokens": 9,
    }


@pytest.mark.asyncio
async def test_gemini_never_fabricates_signature(harness):
    model, requests = harness("google_genai")
    model.model = "gemini-3-pro-preview"
    ai = AIMessage(content="", tool_calls=[{"id": "a", "name": "lookup", "args": {}}])
    with pytest.raises(ModelAccessError, match="capability_error"):
        await model.ainvoke([HumanMessage("q"), ai, ToolMessage("r", tool_call_id="a")])
    assert requests == []


@pytest.mark.parametrize("protocol", ["anthropic_messages", "google_genai"])
def test_explicit_thinking_rules(protocol):
    with pytest.raises(ConfigError):
        config(protocol, thinking="on")
    with pytest.raises(ConfigError):
        config(protocol, thinking="default", thinking_budget=2048)


@pytest.mark.asyncio
async def test_session_display_excludes_native_metadata():
    from types import SimpleNamespace

    from app.services.session_service import get_message_histry

    class Runtime:
        async def aget_state(self, config):
            return SimpleNamespace(
                values={
                    "messages": [
                        AIMessage(
                            content=[
                                {"type": "thinking", "thinking": "private", "signature": "private"},
                                {"type": "text", "text": "visible"},
                            ]
                        )
                    ]
                }
            )

        async def get_pending_approval(self, thread_id):
            return None

    runtime = Runtime()
    runtime.graph = runtime
    assert (await get_message_histry("thread", runtime))[0]["content"] == "visible"


class NestedTopic(BaseModel):
    subject: Literal["math", "science"]


class NestedAnswer(BaseModel):
    topic: NestedTopic
    value: int


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.parametrize("mode", ["valid", "missing", "invalid_enum", "truncated"])
@pytest.mark.asyncio
async def test_structured_actual_parser_preserves_business_validation(protocol, mode, harness):
    args = {"topic": {"subject": "math"}, "value": 7}
    if mode == "missing":
        args.pop("value")
    elif mode == "invalid_enum":
        args["topic"]["subject"] = "unsupported"
    body = json.loads((FIXTURES / f"{protocol}.json").read_text())
    if protocol == "openai_chat":
        body["choices"][0]["message"]["tool_calls"][0]["function"] = {
            "name": "NestedAnswer",
            "arguments": json.dumps(args),
        }
        if mode == "truncated":
            body["choices"][0]["finish_reason"] = "length"
    elif protocol == "anthropic_messages":
        body["content"] = [{"type": "tool_use", "id": "one", "name": "NestedAnswer", "input": args}]
        if mode == "truncated":
            body["stop_reason"] = "max_tokens"
    else:
        body["candidates"][0]["content"]["parts"] = [{"functionCall": {"name": "NestedAnswer", "args": args}}]
        if mode == "truncated":
            body["candidates"][0]["finishReason"] = "MAX_TOKENS"
    model, requests = harness(protocol, handler=lambda r: httpx.Response(200, json=body))
    runnable = model.with_structured_output(NestedAnswer)
    if mode == "valid":
        assert (await runnable.ainvoke("extract")).value == 7
    else:
        with pytest.raises(Exception):
            await runnable.ainvoke("extract")
    assert len(requests) == 1
    payload = json.dumps(json.loads(requests[0].content))
    assert "subject" in payload and "required" in payload and "science" in payload


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_native_schema_strategy(protocol, harness):
    answer = {"topic": {"subject": "math"}, "value": 7}
    body = json.loads((FIXTURES / f"{protocol}.json").read_text())
    if protocol == "openai_chat":
        body["choices"][0]["message"] = {"role": "assistant", "content": json.dumps(answer)}
        body["choices"][0]["finish_reason"] = "stop"
    elif protocol == "anthropic_messages":
        body["content"] = [{"type": "text", "text": json.dumps(answer)}]
        body["stop_reason"] = "end_turn"
    else:
        body["candidates"][0]["content"]["parts"] = [{"text": json.dumps(answer)}]
    model, requests = harness(protocol, handler=lambda r: httpx.Response(200, json=body))
    assert (await model.with_structured_output(NestedAnswer, method="json_schema").ainvoke("extract")).value == 7
    assert "NestedAnswer" in requests[0].content.decode() or "subject" in requests[0].content.decode()


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_create_agent_runs_tool_once_with_middleware(protocol, harness):
    from langchain.agents import create_agent
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.tools import tool

    effects = []
    calls = []

    @tool
    def lookup(topic: str) -> str:
        """Look up a topic."""
        effects.append(topic)
        return "42"

    class Audit(AgentMiddleware):
        async def awrap_model_call(self, request, handler):
            calls.append(1)
            return await handler(request)

    def respond(request):
        body = json.loads((FIXTURES / f"{protocol}.json").read_text())
        if effects:
            if protocol == "openai_chat":
                body["choices"][0]["message"] = {"role": "assistant", "content": "42"}
                body["choices"][0]["finish_reason"] = "stop"
            elif protocol == "anthropic_messages":
                body["content"] = [{"type": "text", "text": "42"}]
                body["stop_reason"] = "end_turn"
            else:
                body["candidates"][0]["content"]["parts"] = [{"text": "42"}]
        return httpx.Response(200, json=body)

    model, _ = harness(protocol, handler=respond)
    agent = create_agent(model, tools=[lookup], middleware=[Audit()])
    result = await agent.ainvoke({"messages": [HumanMessage("lookup math")]})
    assert display_text(result["messages"][-1]) == "42"
    assert effects == ["math"] and len(calls) == 2


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_parallel_results_keep_call_ids(protocol, harness):
    model, requests = harness(protocol)
    reply = AIMessage(
        content="Visible",
        tool_calls=[
            {"name": "lookup", "args": {"topic": "math"}, "id": "first"},
            {"name": "lookup", "args": {"topic": "science"}, "id": "second"},
        ],
        response_metadata={"smartclass_protocol": protocol},
    )
    await model.bind_tools([TOOL]).ainvoke(
        [
            HumanMessage("q"),
            reply,
            ToolMessage("science-result", tool_call_id="second"),
            ToolMessage("math-result", tool_call_id="first"),
        ]
    )
    body = json.loads(requests[-1].content)
    if protocol == "google_genai":
        responses = [p["functionResponse"] for c in body["contents"] for p in c["parts"] if "functionResponse" in p]
        assert [(p["id"], p["response"]["output"]) for p in responses] == [
            ("second", "science-result"),
            ("first", "math-result"),
        ]
        assert "Visible" in requests[-1].content.decode()
    elif protocol == "anthropic_messages":
        responses = body["messages"][-1]["content"]
        assert [(r["tool_use_id"], r["content"]) for r in responses] == [
            ("second", "science-result"),
            ("first", "math-result"),
        ]
    else:
        assert [(r["tool_call_id"], r["content"]) for r in body["messages"][-2:]] == [
            ("second", "science-result"),
            ("first", "math-result"),
        ]


@pytest.mark.parametrize("protocol", ["anthropic_messages", "google_genai"])
@pytest.mark.asyncio
async def test_thinking_mapping_and_no_forced_anthropic(harness, protocol):
    model, requests = harness(protocol)
    # Build via the same adapter with an explicitly declared thinking profile.
    from importlib import import_module

    from app.core.model_access.registry import validate_parameters
    from app.core.model_access.schemas import Parameters

    snapshot = config(protocol)
    profile = snapshot.models["test"].model_copy(
        update={
            "parameters": Parameters(thinking="on", thinking_budget=2048, max_tokens=4096),
            "capabilities": snapshot.models["test"].capabilities.model_copy(
                update={"tool_choice": False, "reasoning_roundtrip": True}
            ),
        }
    )
    connection = snapshot.connections["test"]
    validate_parameters(profile, connection)
    if protocol == "anthropic_messages":
        sync, async_client = model._client._client, model._async_client._client
    else:
        sync, async_client = model.client._api_client._httpx_client, model.client._api_client._async_httpx_client
    thinking_model = import_module("app.core.model_access.adapters." + protocol).build_model(
        profile,
        connection,
        api_key="offline-secret",
        streaming=False,
        sync_client=sync,
        async_client=async_client,
    )
    thinking_model.metadata = {**model.metadata, "smartclass_capabilities": profile.capabilities.model_dump()}
    await thinking_model.bind_tools([TOOL]).ainvoke([HumanMessage("q")])
    body = json.loads(requests[-1].content)
    if protocol == "anthropic_messages":
        assert body["thinking"] == {"type": "enabled", "budget_tokens": 2048}
        with pytest.raises(ConfigError):
            thinking_model.bind_tools([TOOL], tool_choice="lookup")
    else:
        assert body["generationConfig"]["thinkingConfig"]["thinking_budget"] == 2048


@pytest.mark.asyncio
async def test_timeout_budget_prevents_additional_requests(harness):
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(1)
            yield b"{}"

    model, requests = harness("openai_chat", handler=lambda r: httpx.Response(200, stream=Slow()))
    with request_budget(seconds=0.02):
        with pytest.raises(ModelAccessError, match="timeout"):
            await model.ainvoke([HumanMessage("q")])
    assert len(requests) == 1


def test_optional_usage_details_and_no_invented_zero():
    usage = extract_token_usage(
        {
            "usage": {
                "input_tokens": 10,
                "output_tokens": 2,
                "input_token_details": {"cache_read": 3},
                "output_token_details": {"reasoning": 1},
            }
        }
    )
    assert usage["cache_read_tokens"] == 3 and usage["reasoning_tokens"] == 1
    assert "cache_creation_tokens" not in usage
    assert extract_token_usage(None) == {"token_usage_available": False}


def test_old_snapshot_fingerprint_still_restores():
    import hashlib

    from app.core.model_access.schemas import restore_snapshot

    snapshot = config("openai_chat").model_dump(mode="json")
    for profile in snapshot["models"].values():
        profile["parameters"].pop("thinking_budget")
        profile["parameters"].pop("structured_method")
    original = {k: v for k, v in snapshot.items() if k not in {"fingerprint", "rules_version"}}
    snapshot["fingerprint"] = (
        "v1:" + hashlib.sha256(json.dumps(original, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    )
    assert restore_snapshot(snapshot).fingerprint == snapshot["fingerprint"]


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.asyncio
async def test_agent_failure_after_tool_does_not_repeat_effect(protocol, harness):
    from langchain.agents import create_agent
    from langchain_core.tools import tool

    effects = []

    @tool
    def lookup(topic: str) -> str:
        """Look up a topic."""
        effects.append(topic)
        return "42"

    def respond(request):
        if effects:
            return httpx.Response(
                503,
                json={
                    "error": {"code": 503, "message": "private failure", "type": "api_error", "status": "UNAVAILABLE"}
                },
            )
        return httpx.Response(200, json=json.loads((FIXTURES / f"{protocol}.json").read_text()))

    model, requests = harness(protocol, handler=respond)
    with pytest.raises(ModelAccessError, match="server_error"):
        await create_agent(model, tools=[lookup]).ainvoke({"messages": [HumanMessage("lookup math")]})
    assert effects == ["math"] and len(requests) == 3


@pytest.mark.asyncio
async def test_gemini_does_not_drop_schema_constraints(harness):
    model, requests = harness("google_genai")
    schema = {
        "name": "lookup",
        "description": "Constrained lookup",
        "parameters": {
            "type": "object",
            "properties": {"topic": {"type": "string", "allOf": [{"minLength": 2}, {"maxLength": 30}]}},
            "required": ["topic"],
            "additionalProperties": False,
        },
    }
    await model.bind_tools([schema]).ainvoke([HumanMessage("q")])
    declaration = json.loads(requests[0].content)["tools"][0]["functionDeclarations"][0]
    assert declaration.get("parametersJsonSchema", declaration.get("parameters_json_schema")) == schema["parameters"], (
        declaration
    )

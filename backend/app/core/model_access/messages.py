"""Lossless internal history and deliberately lossy public display are separate."""

import asyncio
import time
from copy import deepcopy

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompt_values import ChatPromptValue

from .errors import ModelAccessError, normalized_error, request_budget
from .schemas import ConfigError

PROTOCOL_KEY = "smartclass_protocol"


def display_text(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(
        block if isinstance(block, str) else block["text"]
        for block in content
        if isinstance(block, str)
        or (
            isinstance(block, dict)
            and block.get("type") in {"text", "text_delta"}
            and not block.get("thought")
            and isinstance(block.get("text"), str)
        )
    )


def exchange_boundaries(messages) -> set[int]:
    """Indices at which slicing cannot separate tool calls from results."""
    pending = set()
    boundaries = {0}
    for index, message in enumerate(messages):
        if pending and isinstance(message, (HumanMessage, AIMessage)):
            raise ConfigError("unfinished tool exchange before next conversation message")
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                call_id = call.get("id")
                if not call_id or call_id in pending:
                    raise ConfigError("tool history has missing or duplicate call identifiers")
                pending.add(call_id)
        elif isinstance(message, ToolMessage):
            if message.tool_call_id not in pending:
                raise ConfigError("tool result has no matching call")
            pending.remove(message.tool_call_id)
        if not pending:
            boundaries.add(index + 1)
    return boundaries


def recent_history(messages, limit: int) -> list[BaseMessage]:
    messages = list(messages)
    boundaries = exchange_boundaries(messages)
    target = max(0, len(messages) - limit)
    # Retain leading system context and complete exchanges even if over the limit.
    cutoff = max((i for i in boundaries if i <= target), default=0)
    return [m for m in messages[:cutoff] if isinstance(m, SystemMessage)] + messages[cutoff:]


def source_protocol(message) -> str | None:
    recorded = getattr(message, "response_metadata", {}).get(PROTOCOL_KEY)
    if recorded:
        return recorded
    if "__gemini_function_call_thought_signatures__" in message.additional_kwargs:
        return "google_genai"
    blocks = message.content if isinstance(message.content, list) else []
    if any(isinstance(b, dict) and b.get("type") in {"thinking", "redacted_thinking", "tool_use"} for b in blocks):
        return "anthropic_messages"
    # Persisted history predating protocol tags came exclusively from openai_chat.
    return "openai_chat"


def prepare_history(messages, protocol: str) -> list[BaseMessage]:
    messages = list(messages)
    boundaries = exchange_boundaries(messages)
    switching = any(isinstance(m, AIMessage) and source_protocol(m) not in {None, protocol} for m in messages)
    if switching and len(messages) not in boundaries:
        raise ConfigError("cannot switch protocol during an unfinished tool exchange")
    result = []
    for message in messages:
        if isinstance(message, AIMessage) and source_protocol(message) not in {None, protocol}:
            message = AIMessage(
                content=display_text(message),
                id=message.id,
                name=message.name,
                tool_calls=deepcopy(message.tool_calls),
                response_metadata={PROTOCOL_KEY: protocol},
            )
        result.append(message)
    # Anthropic requires a single initial system envelope. Preserve order and
    # the explicit untrusted memory delimiters; never reclassify it as user text.
    systems = [m for m in result if isinstance(m, SystemMessage)]
    if systems:
        blocks = []
        for m in systems:
            blocks.extend([{"type": "text", "text": m.content}] if isinstance(m.content, str) else deepcopy(m.content))
        result = [SystemMessage(content=blocks), *[m for m in result if not isinstance(m, SystemMessage)]]
    return result


class _CancelledRequest(Exception):
    pass


class ProtocolHistoryMixin:
    """Prepare every invocation (including create_agent), and tag persisted replies."""

    async def agenerate(self, *args, **kwargs):
        # langchain-core 1.2.28 incorrectly treats a child CancelledError as a
        # successful result during on_llm_end. Bridge it across gather unchanged.
        try:
            return await super().agenerate(*args, **kwargs)
        except _CancelledRequest:
            raise asyncio.CancelledError() from None

    def _convert_input(self, value):
        prompt = super()._convert_input(value)
        protocol = (self.metadata or {})[PROTOCOL_KEY]
        return ChatPromptValue(messages=prepare_history(prompt.to_messages(), protocol))

    def _tag(self, message):
        self._check_completion(message)
        message.response_metadata[PROTOCOL_KEY] = (self.metadata or {})[PROTOCOL_KEY]
        return message

    def _check_completion(self, message, info=None):
        metadata = {**message.response_metadata, **(info or {})}
        reason = str(metadata.get("finish_reason") or metadata.get("stop_reason") or "").lower()
        if reason in {"length", "max_tokens", "max_token", "max_output_tokens"}:
            raise ModelAccessError("truncated")
        if reason in {
            "safety",
            "recitation",
            "content_filter",
            "refusal",
            "blocklist",
            "prohibited_content",
        } or message.additional_kwargs.get("refusal"):
            raise ModelAccessError("refusal")

    def _attempt_kwargs(self, kwargs, budget):
        configured = (
            getattr(self, "request_timeout", None)
            or getattr(self, "default_request_timeout", None)
            or getattr(self, "timeout", None)
            or 60
        )
        if not isinstance(configured, (int, float)):
            configured = 60
        return {**kwargs, "timeout": min(configured, budget.seconds)}

    def _generate(self, *args, **kwargs):
        with request_budget() as budget:
            while True:
                budget.take()
                try:
                    result = super()._generate(*args, **self._attempt_kwargs(kwargs, budget))
                    for generation in result.generations:
                        self._check_completion(
                            generation.message, {**(result.llm_output or {}), **(generation.generation_info or {})}
                        )
                        self._tag(generation.message)
                    return result
                except Exception as exc:
                    error = normalized_error(exc)
                    delay = budget.delay(error)
                    if delay is None:
                        raise error from None
                    time.sleep(delay)

    async def _agenerate(self, *args, **kwargs):
        with request_budget() as budget:
            while True:
                budget.take()
                try:
                    async with asyncio.timeout(budget.seconds):
                        result = await super()._agenerate(*args, **self._attempt_kwargs(kwargs, budget))
                    for generation in result.generations:
                        self._check_completion(
                            generation.message, {**(result.llm_output or {}), **(generation.generation_info or {})}
                        )
                        self._tag(generation.message)
                    return result
                except asyncio.CancelledError:
                    raise _CancelledRequest("model request cancelled") from None
                except Exception as exc:
                    error = normalized_error(exc)
                    delay = budget.delay(error)
                    if delay is None:
                        raise error from None
                    await asyncio.sleep(delay)

    def _stream(self, *args, **kwargs):
        with request_budget() as budget:
            while True:
                budget.take()
                committed = False
                try:
                    for chunk in super()._stream(*args, **self._attempt_kwargs(kwargs, budget)):
                        if budget.seconds <= 0:
                            raise ModelAccessError("timeout")
                        self._check_completion(chunk.message, chunk.generation_info)
                        if not committed:
                            self._tag(chunk.message)
                        committed = True
                        yield chunk
                    return
                except Exception as exc:
                    error = normalized_error(exc)
                    delay = None if committed else budget.delay(error)
                    if delay is None:
                        raise error from None
                    time.sleep(delay)

    async def _astream(self, *args, **kwargs):
        with request_budget() as budget:
            while True:
                budget.take()
                committed = False
                try:
                    async with asyncio.timeout(budget.seconds):
                        async for chunk in super()._astream(*args, **self._attempt_kwargs(kwargs, budget)):
                            self._check_completion(chunk.message, chunk.generation_info)
                            if not committed:
                                self._tag(chunk.message)
                            committed = True
                            yield chunk
                    return
                except Exception as exc:
                    error = normalized_error(exc)
                    delay = None if committed else budget.delay(error)
                    if delay is None:
                        raise error from None
                    await asyncio.sleep(delay)

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        caps = (self.metadata or {}).get("smartclass_capabilities", {})
        if not caps.get("tools"):
            raise ConfigError("tools capability is unsupported or undeclared")
        if tool_choice not in (None, "auto", "none") and not caps.get("tool_choice"):
            raise ConfigError("forced tool choice is unsupported or undeclared")
        return super().bind_tools(tools, tool_choice=tool_choice, **kwargs)

    def with_structured_output(self, schema=None, *, method=None, **kwargs):
        configured = (self.metadata or {}).get("smartclass_structured_method", "tool_calling")
        method = method or ("function_calling" if configured == "tool_calling" else "json_schema")
        caps = (self.metadata or {}).get("smartclass_capabilities", {})
        if method == "json_schema" and not caps.get("structured"):
            raise ConfigError("native schema capability is unsupported or undeclared")
        if method == "function_calling" and not (caps.get("tools") and caps.get("tool_choice")):
            raise ConfigError("structured tool strategy requires forced tool choice")
        if method not in {"json_schema", "function_calling"}:
            raise ConfigError("unsupported structured strategy")
        return super().with_structured_output(schema, method=method, **kwargs)

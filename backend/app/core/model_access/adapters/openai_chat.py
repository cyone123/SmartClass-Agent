from __future__ import annotations

from typing import Any

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from ..messages import ProtocolHistoryMixin
from ..schemas import Connection, ModelProfile


class RuntimeChatModel(ProtocolHistoryMixin, ChatOpenAI):
    """OpenAI-compatible model with provider continuation metadata preserved."""

    preserve_reasoning_content: bool = False
    expose_upstream_metadata: bool = False

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if not self.preserve_reasoning_content or "messages" not in payload:
            return payload
        prepared = self._convert_input(input_).to_messages()
        for message, serialized in zip(prepared, payload["messages"], strict=True):
            if isinstance(message, AIMessage) and "reasoning_content" in message.additional_kwargs:
                serialized["reasoning_content"] = message.additional_kwargs["reasoning_content"]
        return payload

    def _create_chat_result(self, response, generation_info=None):
        response_dict = response if isinstance(response, dict) else response.model_dump(warnings=False)
        result = super()._create_chat_result(response, generation_info)
        for choice, generation in zip(response_dict.get("choices") or (), result.generations, strict=True):
            reasoning = (choice.get("message") or {}).get("reasoning_content")
            if self.preserve_reasoning_content and reasoning is not None:
                generation.message.additional_kwargs["reasoning_content"] = reasoning
            upstream = _actual_upstream(response_dict)
            if self.expose_upstream_metadata:
                generation.message.response_metadata["smartclass_actual_upstream"] = upstream
        return result

    def _convert_chunk_to_generation_chunk(self, chunk, default_chunk_class, base_generation_info):
        generation = super()._convert_chunk_to_generation_chunk(chunk, default_chunk_class, base_generation_info)
        choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices") or ()
        if generation is not None and choices:
            reasoning = (choices[0].get("delta") or {}).get("reasoning_content")
            if self.preserve_reasoning_content and reasoning is not None:
                generation.message.additional_kwargs["reasoning_content"] = reasoning
            if self.expose_upstream_metadata:
                generation.message.response_metadata["smartclass_actual_upstream"] = _actual_upstream(chunk)
        return generation


def _actual_upstream(response: dict[str, Any]) -> str:
    metadata = response.get("openrouter_metadata") or {}
    value = response.get("provider") or metadata.get("provider") or metadata.get("provider_name")
    return value if isinstance(value, str) and value.strip() else "unknown"


def build_model(
    profile: ModelProfile,
    connection: Connection,
    *,
    api_key: str,
    streaming: bool,
    sync_client: httpx.Client,
    async_client: httpx.AsyncClient,
) -> BaseChatModel:
    params = profile.parameters.model_dump(
        exclude_none=True,
        exclude={
            "thinking",
            "thinking_budget",
            "reasoning_effort",
            "provider_routing",
            "structured_method",
        },
    )
    extra_body: dict[str, Any] = {}
    if connection.preset == "openrouter":
        routing = profile.parameters.provider_routing
        extra_body["provider"] = (
            routing.request_value() if routing else {"allow_fallbacks": True, "require_parameters": True}
        )
        if profile.parameters.reasoning_effort:
            extra_body["reasoning"] = {"effort": profile.parameters.reasoning_effort}
        elif profile.parameters.thinking != "default":
            extra_body["reasoning"] = {"effort": "high" if profile.parameters.thinking == "on" else "none"}
    elif profile.parameters.thinking != "default":
        extra_body["thinking"] = {"type": "enabled" if profile.parameters.thinking == "on" else "disabled"}
    if connection.preset == "deepseek" and profile.parameters.reasoning_effort:
        params["reasoning_effort"] = profile.parameters.reasoning_effort
    if extra_body:
        params["extra_body"] = extra_body
    return RuntimeChatModel(
        model=profile.model_id,
        api_key=api_key,
        base_url=connection.endpoint,
        streaming=streaming,
        max_retries=0,
        **({"stream_usage": True} if streaming else {}),
        http_client=sync_client,
        http_async_client=async_client,
        preserve_reasoning_content=connection.preset in {"deepseek", "zhipu"},
        expose_upstream_metadata=connection.preset == "openrouter",
        **params,
    )

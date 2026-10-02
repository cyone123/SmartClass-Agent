"""Pinned ChatAnthropic integration with factory-owned transports."""

import anthropic
from langchain_anthropic import ChatAnthropic

from ..messages import ProtocolHistoryMixin
from ..schemas import Connection, ModelProfile


class RuntimeChatModel(ProtocolHistoryMixin, ChatAnthropic):
    pass


def build_model(profile: ModelProfile, connection: Connection, *, api_key, streaming, sync_client, async_client):
    p = profile.parameters
    kwargs = {}
    if p.temperature is not None:
        kwargs["temperature"] = p.temperature
    if p.thinking != "default":
        kwargs["thinking"] = {"type": {"on": "enabled", "off": "disabled", "adaptive": "adaptive"}[p.thinking]}
        if p.thinking_budget is not None:
            kwargs["thinking"]["budget_tokens"] = p.thinking_budget
    model = RuntimeChatModel(
        model=profile.model_id,
        api_key=api_key,
        base_url=connection.endpoint,
        max_tokens=p.max_tokens or 4096,
        timeout=p.timeout or 60,
        max_retries=0,
        streaming=streaming,
        stream_usage=True,
        **kwargs,
    )
    # These cached properties otherwise create globally cached SDK HTTP clients.
    model.__dict__["_client"] = anthropic.Anthropic(
        api_key=api_key,
        base_url=connection.endpoint,
        max_retries=0,
        timeout=p.timeout or 60,
        http_client=sync_client,
    )
    model.__dict__["_async_client"] = anthropic.AsyncAnthropic(
        api_key=api_key,
        base_url=connection.endpoint,
        max_retries=0,
        timeout=p.timeout or 60,
        http_client=async_client,
    )
    return model

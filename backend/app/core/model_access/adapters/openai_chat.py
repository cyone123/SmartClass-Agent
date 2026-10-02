from __future__ import annotations

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from ..messages import ProtocolHistoryMixin
from ..schemas import Connection, ModelProfile


class RuntimeChatModel(ProtocolHistoryMixin, ChatOpenAI):
    pass


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
        exclude_none=True, exclude={"thinking", "thinking_budget", "structured_method"}
    )
    if profile.parameters.thinking != "default":
        params["extra_body"] = {"thinking": {"type": "enabled" if profile.parameters.thinking == "on" else "disabled"}}
    return RuntimeChatModel(
        model=profile.model_id,
        api_key=api_key,
        base_url=connection.endpoint,
        streaming=streaming,
        max_retries=0,
        **({"stream_usage": True} if streaming else {}),
        http_client=sync_client,
        http_async_client=async_client,
        **params,
    )

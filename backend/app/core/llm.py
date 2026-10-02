from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel
from langchain_openai import OpenAIEmbeddings

from app.config import get_experience_memory_embedding_dimensions
from app.core.model_access import get_role_model


def get_model(*, streaming: bool = False) -> BaseChatModel:
    return get_role_model("main", streaming=streaming)


def get_structured_output_model(*, streaming: bool = False) -> BaseChatModel:
    return get_role_model("structured", streaming=streaming)


def get_small_model(*, streaming: bool = False) -> BaseChatModel:
    return get_role_model("small", streaming=streaming)


def get_memory_model(*, streaming: bool = False) -> BaseChatModel:
    return get_role_model("memory", streaming=streaming)


def get_context_compression_llm(*, streaming: bool = False) -> BaseChatModel:
    return get_role_model("compression", streaming=streaming)


def get_structured_fast_model(*, streaming: bool = False) -> BaseChatModel:
    return get_role_model("structured_fast", streaming=streaming)


def get_embeddings_model() -> OpenAIEmbeddings:
    """Return the configured OpenAI-compatible embeddings role."""

    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDINGS_MODEL"),
        api_key=os.getenv("EMBEDDINGS_API_KEY"),
        base_url=os.getenv("EMBEDDINGS_BASE_URL"),
        dimensions=get_experience_memory_embedding_dimensions(),
        check_embedding_ctx_length=False,
    )


def is_structured_fallback_enabled() -> bool:
    return os.getenv("STRUCTURED_FALLBACK_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

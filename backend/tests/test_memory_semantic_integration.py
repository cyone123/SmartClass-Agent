from __future__ import annotations

import asyncio
import selectors
import sys
from uuid import uuid4

import pytest
from langchain_core.embeddings import Embeddings
from langgraph.store.postgres.aio import AsyncPostgresStore

from app.config import get_db_uri

pytestmark = pytest.mark.integration


class DeterministicEmbeddings(Embeddings):
    dimensions = 3072

    @classmethod
    def _vector(cls, text: str) -> list[float]:
        vector = [0.0] * cls.dimensions
        if "二次函数" in text or "函数图像" in text:
            vector[0] = 1.0
        else:
            vector[1] = 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def test_postgres_store_semantic_search_returns_scores_and_relevance_order() -> None:
    async def run() -> None:
        namespace = ("users", f"semantic-test-{uuid4().hex}", "experiences")
        index = {
            "dims": DeterministicEmbeddings.dimensions,
            "embed": DeterministicEmbeddings(),
            "fields": ["title", "summary", "tags"],
            "ann_index_config": {"vector_type": "halfvec"},
        }
        async with AsyncPostgresStore.from_conn_string(get_db_uri(), index=index) as store:
            await store.setup()
            try:
                await store.aput(
                    namespace,
                    "relevant",
                    {"title": "二次函数图像", "summary": "用图像探究函数性质", "tags": ["数学"]},
                    index=["title", "summary", "tags"],
                )
                await store.aput(
                    namespace,
                    "unrelated",
                    {"title": "古诗朗读", "summary": "用配乐组织朗读", "tags": ["语文"]},
                    index=["title", "summary", "tags"],
                )
                results = await store.asearch(namespace, query="二次函数的图像教学", limit=2)
                assert results[0].key == "relevant"
                assert results[0].score is not None
                assert results[1].score is not None
                assert results[0].score > results[1].score
            finally:
                await store.adelete(namespace, "relevant")
                await store.adelete(namespace, "unrelated")

    if sys.platform == "win32":
        asyncio.run(run(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(run())

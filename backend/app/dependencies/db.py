import asyncio

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import (
    get_db_uri,
    get_env,
    get_experience_memory_embedding_dimensions,
    get_experience_memory_index_fields,
    get_experience_memory_semantic_enabled,
    get_sqlalchemy_echo,
)
from app.core.llm import get_embeddings_model
from app.models import Base


def build_memory_store_index_config() -> dict[str, object] | None:
    if not get_experience_memory_semantic_enabled():
        return None
    if not (get_env("EMBEDDINGS_MODEL") or "").strip():
        raise ValueError("EMBEDDINGS_MODEL is required when EXPERIENCE_MEMORY_SEMANTIC_ENABLED is enabled.")
    return {
        "dims": get_experience_memory_embedding_dimensions(),
        "embed": get_embeddings_model(),
        "fields": list(get_experience_memory_index_fields()),
        "ann_index_config": {"vector_type": "halfvec"},
    }


async def validate_memory_store_semantic_schema(
    pool: AsyncConnectionPool,
    *,
    expected_dims: int,
    expected_vector_type: str = "halfvec",
) -> None:
    """Fail startup when an existing LangGraph vector schema is incompatible."""

    async with pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT
                    (
                        SELECT format_type(attribute.atttypid, attribute.atttypmod)
                        FROM pg_attribute AS attribute
                        JOIN pg_class AS relation ON relation.oid = attribute.attrelid
                        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                        WHERE namespace.nspname = current_schema()
                          AND relation.relname = 'store_vectors'
                          AND attribute.attname = 'embedding'
                          AND NOT attribute.attisdropped
                    ) AS embedding_type,
                    to_regclass(current_schema() || '.store_vectors_embedding_idx') IS NOT NULL AS has_ann_index
                """
            )
            row = await cursor.fetchone()
    expected_type = f"{expected_vector_type}({expected_dims})"
    if not row or row.get("embedding_type") != expected_type or not row.get("has_ann_index"):
        actual_type = row.get("embedding_type") if row else None
        raise RuntimeError(
            "Experience semantic memory schema is incompatible: "
            f"expected {expected_type} with ANN index, found {actual_type or 'missing vector column'}."
        )


class PostgresProvider:
    _checkpoint_lock: asyncio.Lock | None = None
    _checkpoint_pool: AsyncConnectionPool | None = None
    _checkpoint_saver: AsyncPostgresSaver | None = None
    _memory_lock: asyncio.Lock | None = None
    _memory_pool: AsyncConnectionPool | None = None
    _memory_store: AsyncPostgresStore | None = None

    @staticmethod
    def get_db_conn_string() -> str:
        return get_db_uri()

    @classmethod
    def get_checkpoint_lock(cls) -> asyncio.Lock:
        if cls._checkpoint_lock is None:
            cls._checkpoint_lock = asyncio.Lock()
        return cls._checkpoint_lock

    @classmethod
    def get_memory_lock(cls) -> asyncio.Lock:
        if cls._memory_lock is None:
            cls._memory_lock = asyncio.Lock()
        return cls._memory_lock

    @classmethod
    async def init_agent_checkpointer(cls) -> AsyncPostgresSaver:
        if cls._checkpoint_saver is not None:
            return cls._checkpoint_saver

        async with cls.get_checkpoint_lock():
            if cls._checkpoint_saver is None:
                pool = AsyncConnectionPool(
                    conninfo=cls.get_db_conn_string(),
                    kwargs={
                        "autocommit": True,
                        "prepare_threshold": 0,
                        "row_factory": dict_row,
                    },
                    min_size=4,
                    max_size=20,
                    open=False,
                    name="langgraph-checkpoint-pool",
                )
                await pool.open(wait=True)

                saver = AsyncPostgresSaver(conn=pool)
                await saver.setup()

                cls._checkpoint_pool = pool
                cls._checkpoint_saver = saver

        return cls._checkpoint_saver

    @classmethod
    def get_agent_checkpointer(cls) -> AsyncPostgresSaver:
        if cls._checkpoint_saver is None:
            raise RuntimeError("Agent checkpointer is not initialized.")
        return cls._checkpoint_saver

    @classmethod
    async def init_memory_store(cls) -> AsyncPostgresStore:
        if cls._memory_store is not None:
            return cls._memory_store

        async with cls.get_memory_lock():
            if cls._memory_store is None:
                pool = AsyncConnectionPool(
                    conninfo=cls.get_db_conn_string(),
                    kwargs={
                        "autocommit": True,
                        "prepare_threshold": 0,
                        "row_factory": dict_row,
                    },
                    min_size=2,
                    max_size=10,
                    open=False,
                    name="langgraph-memory-store-pool",
                )
                await pool.open(wait=True)

                try:
                    index = build_memory_store_index_config()
                except Exception:
                    await pool.close()
                    raise
                store = AsyncPostgresStore(conn=pool, index=index)
                try:
                    await store.setup()
                except Exception:
                    await pool.close()
                    raise

                if get_experience_memory_semantic_enabled() and not store.index_config:
                    await pool.close()
                    raise RuntimeError("Experience semantic memory index is unavailable after Store setup.")
                if get_experience_memory_semantic_enabled():
                    try:
                        await validate_memory_store_semantic_schema(
                            pool,
                            expected_dims=get_experience_memory_embedding_dimensions(),
                        )
                    except Exception:
                        await pool.close()
                        raise

                cls._memory_pool = pool
                cls._memory_store = store

        return cls._memory_store

    @classmethod
    def get_memory_store(cls) -> AsyncPostgresStore:
        if cls._memory_store is None:
            raise RuntimeError("Memory store is not initialized.")
        return cls._memory_store

    @classmethod
    async def close_agent_resources(cls) -> None:
        async with cls.get_checkpoint_lock():
            pool = cls._checkpoint_pool
            cls._checkpoint_pool = None
            cls._checkpoint_saver = None

        if pool is not None:
            await pool.close()

        async with cls.get_memory_lock():
            memory_pool = cls._memory_pool
            cls._memory_pool = None
            cls._memory_store = None

        if memory_pool is not None:
            await memory_pool.close()


def get_agent_checkpointer() -> AsyncPostgresSaver:
    return PostgresProvider.get_agent_checkpointer()


async def init_agent_checkpointer() -> AsyncPostgresSaver:
    return await PostgresProvider.init_agent_checkpointer()


def get_memory_store() -> AsyncPostgresStore:
    return PostgresProvider.get_memory_store()


async def init_memory_store() -> AsyncPostgresStore:
    return await PostgresProvider.init_memory_store()


def get_async_db_uri() -> str:
    uri = PostgresProvider.get_db_conn_string()
    if uri.startswith("postgresql://"):
        return "postgresql+asyncpg://" + uri[len("postgresql://") :]
    if uri.startswith("postgres://"):
        return "postgresql+asyncpg://" + uri[len("postgres://") :]
    raise ValueError(f"Unsupported database URI scheme in {uri}")


async_engine = create_async_engine(
    get_async_db_uri(),
    echo=get_sqlalchemy_echo(),
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.services.auth_service import ensure_default_admin

    async with AsyncSessionLocal() as session:
        await ensure_default_admin(session)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_agent_checkpointer() -> None:
    await PostgresProvider.close_agent_resources()


async def close_db_resources() -> None:
    await async_engine.dispose()

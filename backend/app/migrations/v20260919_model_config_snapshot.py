"""Run explicitly before deploying the model runtime; nullable and idempotent."""

from __future__ import annotations

import asyncio

import asyncpg

from app.config import get_db_uri

VERSION = "20260919_model_config_snapshot"
DDL = "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS model_config_snapshot JSON NULL;"


async def upgrade(connection) -> str:
    await connection.execute(DDL)
    return "ready"


async def _run() -> None:
    connection = await asyncpg.connect(get_db_uri())
    try:
        result = await upgrade(connection)
    finally:
        await connection.close()
    print(f"{VERSION}: {result}")


if __name__ == "__main__":
    asyncio.run(_run())

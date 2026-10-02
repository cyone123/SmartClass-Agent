from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from app.config import get_db_uri

VERSION = "20260907_drop_agent_run_events"


async def upgrade(connection: Any) -> str:
    table_name = await connection.fetchval("SELECT to_regclass('public.agent_run_events')")
    if table_name is None:
        return "missing"

    has_rows = await connection.fetchval("SELECT EXISTS (SELECT 1 FROM public.agent_run_events LIMIT 1)")
    if has_rows:
        raise RuntimeError(
            "Schema upgrade refused: agent_run_events is not empty. Drain runs and resolve retained data first."
        )

    async with connection.transaction():
        await connection.execute("LOCK TABLE public.agent_run_events IN ACCESS EXCLUSIVE MODE")
        has_rows = await connection.fetchval("SELECT EXISTS (SELECT 1 FROM public.agent_run_events LIMIT 1)")
        if has_rows:
            raise RuntimeError(
                "Schema upgrade refused: agent_run_events became non-empty while acquiring the migration lock."
            )
        await connection.execute("DROP TABLE public.agent_run_events")
    return "dropped"


async def _run() -> None:
    connection = await asyncpg.connect(get_db_uri())
    try:
        result = await upgrade(connection)
    finally:
        await connection.close()
    print(f"{VERSION}: {result}")


if __name__ == "__main__":
    asyncio.run(_run())

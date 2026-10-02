from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.memory import backfill_experience_memory_index  # noqa: E402
from app.dependencies.db import PostgresProvider  # noqa: E402


async def _run(batch_size: int) -> int:
    try:
        store = await PostgresProvider.init_memory_store()
        result = await backfill_experience_memory_index(store, batch_size=batch_size)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1 if result["failed_count"] else 0
    finally:
        await PostgresProvider.close_agent_resources()


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser(description="Backfill semantic vectors for existing Experience memories.")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    return asyncio.run(_run(args.batch_size))


if __name__ == "__main__":
    raise SystemExit(main())

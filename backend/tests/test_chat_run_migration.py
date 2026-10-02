from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager

import pytest

from app.migrations.v20260907_drop_agent_run_events import upgrade


class _Transaction(AbstractAsyncContextManager):
    async def __aexit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb


class _Connection:
    def __init__(self, *, exists: bool, rows: list[bool]) -> None:
        self.exists = exists
        self.rows = list(rows)
        self.executed: list[str] = []

    async def fetchval(self, statement: str):
        if "to_regclass" in statement:
            return "agent_run_events" if self.exists else None
        if "SELECT EXISTS" in statement:
            return self.rows.pop(0)
        raise AssertionError(statement)

    async def execute(self, statement: str):
        self.executed.append(statement)

    def transaction(self):
        return _Transaction()


def test_schema_upgrade_is_idempotent_when_table_is_missing() -> None:
    connection = _Connection(exists=False, rows=[])
    assert asyncio.run(upgrade(connection)) == "missing"
    assert connection.executed == []


def test_schema_upgrade_refuses_non_empty_event_table() -> None:
    connection = _Connection(exists=True, rows=[True])
    with pytest.raises(RuntimeError, match="not empty"):
        asyncio.run(upgrade(connection))
    assert not any(statement.startswith("DROP TABLE") for statement in connection.executed)


def test_schema_upgrade_locks_rechecks_and_drops_empty_event_table() -> None:
    connection = _Connection(exists=True, rows=[False, False])
    assert asyncio.run(upgrade(connection)) == "dropped"
    assert connection.executed == [
        "LOCK TABLE public.agent_run_events IN ACCESS EXCLUSIVE MODE",
        "DROP TABLE public.agent_run_events",
    ]

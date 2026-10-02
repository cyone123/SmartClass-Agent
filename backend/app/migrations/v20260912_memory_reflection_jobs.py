from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from app.config import get_db_uri

VERSION = "20260912_memory_reflection_jobs"

DDL = """
CREATE TABLE IF NOT EXISTS memory_reflection_jobs (
    job_id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    source_run_id VARCHAR(64) NOT NULL,
    source_thread_id VARCHAR(255) NOT NULL,
    source_plan_id INTEGER NULL,
    kind VARCHAR(16) NOT NULL,
    business_stage VARCHAR(48) NOT NULL,
    extractor_version VARCHAR(32) NOT NULL,
    snapshot_version INTEGER NOT NULL DEFAULT 1,
    snapshot JSON NOT NULL,
    evidence_type VARCHAR(48) NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    error_category VARCHAR(48) NULL,
    error_message TEXT NULL,
    applied_memory_id VARCHAR(64) NULL,
    applied_memory_version INTEGER NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL,
    CONSTRAINT uq_memory_reflection_job_idempotency
        UNIQUE (user_id, source_run_id, kind, business_stage, extractor_version)
);
CREATE INDEX IF NOT EXISTS ix_memory_reflection_jobs_user_id ON memory_reflection_jobs(user_id);
CREATE INDEX IF NOT EXISTS ix_memory_reflection_jobs_source_run_id ON memory_reflection_jobs(source_run_id);
CREATE INDEX IF NOT EXISTS ix_memory_reflection_jobs_status ON memory_reflection_jobs(status);
CREATE INDEX IF NOT EXISTS ix_memory_reflection_jobs_pending
    ON memory_reflection_jobs(status, created_at);

UPDATE memory_reflection_jobs SET status = 'pending' WHERE status = 'retry';
DROP INDEX IF EXISTS ix_memory_reflection_jobs_claim;
ALTER TABLE memory_reflection_jobs DROP COLUMN IF EXISTS attempts;
ALTER TABLE memory_reflection_jobs DROP COLUMN IF EXISTS available_at;
ALTER TABLE memory_reflection_jobs DROP COLUMN IF EXISTS lease_owner;
ALTER TABLE memory_reflection_jobs DROP COLUMN IF EXISTS lease_expires_at;

CREATE TABLE IF NOT EXISTS memory_mutation_guards (
    guard_id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    kind VARCHAR(16) NOT NULL,
    memory_id VARCHAR(64) NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    deletion_generation INTEGER NOT NULL DEFAULT 0,
    deleted_at TIMESTAMPTZ NULL,
    last_manual_mutation_at TIMESTAMPTZ NULL,
    last_applied_job_id VARCHAR(32) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_memory_mutation_guard_target UNIQUE (user_id, kind, memory_id)
);
CREATE INDEX IF NOT EXISTS ix_memory_mutation_guards_user_id ON memory_mutation_guards(user_id);
"""


async def upgrade(connection: Any) -> str:
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

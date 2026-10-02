from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class Scenario:
    name: str
    legacy_model_calls: int
    simplified_model_calls: int
    visible_latency_kind: str


SCENARIOS = (
    Scenario("ordinary_chat", 2, 1, "first_token_latency_ms"),
    Scenario("memory_assisted_chat", 2, 2, "first_token_latency_ms"),
    Scenario("first_incomplete_teaching_request", 3, 2, "clarification_latency_ms"),
    Scenario("clarification_turn", 2, 1, "clarification_latency_ms"),
    Scenario("complete_teaching_request", 2, 2, "approval_latency_ms"),
)


async def _run_controlled_calls(call_count: int, delay_seconds: float) -> float:
    started = time.perf_counter()
    for _ in range(call_count):
        await asyncio.sleep(delay_seconds)
    return (time.perf_counter() - started) * 1000


async def build_report(*, repeats: int = 20, delay_ms: float = 10.0) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    delay_seconds = delay_ms / 1000
    for scenario in SCENARIOS:
        legacy_samples = [
            await _run_controlled_calls(scenario.legacy_model_calls, delay_seconds) for _ in range(repeats)
        ]
        simplified_samples = [
            await _run_controlled_calls(scenario.simplified_model_calls, delay_seconds) for _ in range(repeats)
        ]
        legacy_latency = statistics.median(legacy_samples)
        simplified_latency = statistics.median(simplified_samples)
        rows.append(
            {
                "scenario": scenario.name,
                "legacy": {
                    "model_calls": scenario.legacy_model_calls,
                    scenario.visible_latency_kind: round(legacy_latency, 3),
                },
                "simplified": {
                    "model_calls": scenario.simplified_model_calls,
                    scenario.visible_latency_kind: round(simplified_latency, 3),
                },
                "model_call_reduction": scenario.legacy_model_calls - scenario.simplified_model_calls,
                "latency_proxy_reduction_percent": round(
                    (1 - simplified_latency / legacy_latency) * 100 if legacy_latency else 0,
                    2,
                ),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_mode": "deterministic",
        "measurement": "controlled-delay orchestration proxy",
        "limitations": (
            "Measures orchestration model-call depth with a fixed async delay; it is not production provider latency."
        ),
        "repeats": repeats,
        "delay_per_model_call_ms": delay_ms,
        "environment": {"os": platform.system(), "python": platform.python_version()},
        "timestamp": datetime.now(UTC).isoformat(),
        "scenarios": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare legacy and simplified main-graph orchestration depth.")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--delay-ms", type=float, default=10.0)
    args = parser.parse_args()
    if args.repeats < 1 or args.delay_ms < 0:
        parser.error("--repeats must be positive and --delay-ms must be non-negative")
    report = asyncio.run(build_report(repeats=args.repeats, delay_ms=args.delay_ms))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

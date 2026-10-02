from __future__ import annotations

import pytest

from tests.benchmarks.main_graph_orchestration_ab import build_report


@pytest.mark.asyncio
async def test_main_graph_report_separates_scenarios_and_metrics() -> None:
    report = await build_report(repeats=1, delay_ms=0)
    rows = {row["scenario"]: row for row in report["scenarios"]}
    assert report["run_mode"] == "deterministic"
    assert rows["ordinary_chat"]["legacy"]["model_calls"] == 2
    assert rows["ordinary_chat"]["simplified"]["model_calls"] == 1
    assert rows["first_incomplete_teaching_request"]["legacy"]["model_calls"] == 3
    assert rows["clarification_turn"]["simplified"]["model_calls"] == 1
    assert "first_token_latency_ms" in rows["memory_assisted_chat"]["simplified"]
    assert "clarification_latency_ms" in rows["clarification_turn"]["simplified"]
    assert "approval_latency_ms" in rows["complete_teaching_request"]["simplified"]
    assert "avg_score" not in report

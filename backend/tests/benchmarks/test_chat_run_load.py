from __future__ import annotations

from tests.benchmarks.chat_run_load_metrics import RunMeasurement, aggregate_chat_run_load


def test_chat_run_load_report_covers_redis_replay_batching_and_postgres_avoidance() -> None:
    before = """
smartclass_chat_run_redis_operations_total{operation="append",event_type="token"} 2
smartclass_chat_run_redis_operation_duration_seconds_sum 0.1
smartclass_chat_run_redis_operation_duration_seconds_count 2
smartclass_chat_run_redis_token_fragments_total 4
"""
    after = """
smartclass_chat_run_redis_operations_total{operation="append",event_type="token"} 5
smartclass_chat_run_redis_operations_total{operation="replay",event_type="unknown"} 4
smartclass_chat_run_redis_operation_duration_seconds_sum 0.25
smartclass_chat_run_redis_operation_duration_seconds_count 7
smartclass_chat_run_redis_token_fragments_total 13
"""
    metrics = aggregate_chat_run_load(
        [
            RunMeasurement(8, 3, 2, 12.0, 1024),
            RunMeasurement(12, 4, 2, 20.0, 2048),
        ],
        before,
        after,
    )

    assert metrics["events_per_run"] == 10
    assert metrics["sse_connection_count"] == 4
    assert metrics["replay_latency_ms"] == {"p50": 12.0, "p95": 20.0}
    assert metrics["redis_operations"] == 7
    assert metrics["redis_operation_avg_latency_ms"] == 30
    assert metrics["token_batching_ratio"] == 3
    assert metrics["retained_memory_bytes_per_run"] == 1536
    assert metrics["postgres_event_statements_observed"] == 0
    assert metrics["postgres_event_transactions_avoided_estimate"] == 20

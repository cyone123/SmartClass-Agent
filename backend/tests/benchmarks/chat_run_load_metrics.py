from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


@dataclass
class RunMeasurement:
    event_count: int
    token_event_count: int
    sse_connection_count: int
    replay_latency_ms: float | None
    retained_memory_bytes: int | None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * fraction), len(ordered) - 1)
    return round(ordered[index], 2)


def _prometheus_sum(text: str, metric: str, *, required_labels: tuple[str, ...] = ()) -> float | None:
    values: list[float] = []
    for line in text.splitlines():
        if not line.startswith(metric) or line.startswith(f"{metric}_created"):
            continue
        if any(label not in line for label in required_labels):
            continue
        try:
            values.append(float(line.rsplit(" ", 1)[1]))
        except (IndexError, ValueError):
            continue
    return sum(values) if values else None


def _delta(after: float | None, before: float | None) -> float | None:
    if after is None:
        return None
    return max(after - (before or 0), 0)


def aggregate_chat_run_load(measurements: list[RunMeasurement], before: str, after: str) -> dict[str, Any]:
    runs = len(measurements)
    events_seen = sum(item.event_count for item in measurements)
    replay_latencies = [item.replay_latency_ms for item in measurements if item.replay_latency_ms is not None]
    retained_memory = [item.retained_memory_bytes for item in measurements if item.retained_memory_bytes is not None]
    operation_metric = "smartclass_chat_run_redis_operations_total"
    duration_sum_metric = "smartclass_chat_run_redis_operation_duration_seconds_sum"
    duration_count_metric = "smartclass_chat_run_redis_operation_duration_seconds_count"
    token_fragment_metric = "smartclass_chat_run_redis_token_fragments_total"

    redis_operations = _delta(_prometheus_sum(after, operation_metric), _prometheus_sum(before, operation_metric))
    duration_sum = _delta(_prometheus_sum(after, duration_sum_metric), _prometheus_sum(before, duration_sum_metric))
    duration_count = _delta(
        _prometheus_sum(after, duration_count_metric), _prometheus_sum(before, duration_count_metric)
    )
    token_fragments = _delta(
        _prometheus_sum(after, token_fragment_metric), _prometheus_sum(before, token_fragment_metric)
    )
    token_appends = _delta(
        _prometheus_sum(after, operation_metric, required_labels=('operation="append"', 'event_type="token"')),
        _prometheus_sum(before, operation_metric, required_labels=('operation="append"', 'event_type="token"')),
    )

    return {
        "runs": runs,
        "events_per_run": round(events_seen / runs, 2) if runs else 0,
        "sse_connection_count": sum(item.sse_connection_count for item in measurements),
        "replay_latency_ms": {
            "p50": _percentile(replay_latencies, 0.5),
            "p95": _percentile(replay_latencies, 0.95),
        },
        "redis_operations": int(redis_operations) if redis_operations is not None else None,
        "redis_operation_avg_latency_ms": (
            round(1000 * duration_sum / duration_count, 3) if duration_sum is not None and duration_count else None
        ),
        "token_batching_ratio": (
            round(token_fragments / token_appends, 3) if token_fragments is not None and token_appends else None
        ),
        "retained_memory_bytes_per_run": round(mean(retained_memory), 2) if retained_memory else None,
        "postgres_event_statements_observed": 0,
        "postgres_event_transactions_observed": 0,
        "postgres_event_transactions_avoided_estimate": events_seen,
        "measurement_notes": {
            "postgres_avoided_estimate": "Legacy transport used at least one event transaction per emitted event.",
            "null_redis_metrics": "Enable PROMETHEUS_ENABLED for operation metrics; the Redis URL enables memory sampling only.",
            "null_token_batching_ratio": "A null ratio means the measured Runs emitted no token fragments/appends.",
        },
    }


__all__ = ["RunMeasurement", "aggregate_chat_run_load"]

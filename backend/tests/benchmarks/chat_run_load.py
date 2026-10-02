"""Locust workload and aggregate report for Redis-backed durable chat runs.

Set SMARTCLASS_BENCHMARK_PLAN_ID and authentication variables, then run:
  python -m locust -f tests/benchmarks/chat_run_load.py --headless --host http://127.0.0.1:8000 ...

Each Locust user creates a private conversation thread, deliberately detaches
one SSE subscriber, and reconnects with an integer cursor. The optional
SMARTCLASS_BENCHMARK_REDIS_URL enables aggregate retained-memory sampling.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from locust import HttpUser, between, events, task
from locust.env import Environment
from locust.exception import StopUser

from app.core.chat_run_events import chat_run_redis_keys
from tests.benchmarks.chat_run_load_metrics import RunMeasurement, aggregate_chat_run_load

PROMPT = os.getenv("SMARTCLASS_BENCHMARK_PROMPT", "请用一句中文回复：Redis chat run load probe 已收到。")
CONNECT_TIMEOUT_SECONDS = float(os.getenv("SMARTCLASS_BENCHMARK_CONNECT_TIMEOUT_SECONDS", "10"))
READ_TIMEOUT_SECONDS = float(os.getenv("SMARTCLASS_BENCHMARK_READ_TIMEOUT_SECONDS", "180"))
OUTPUT_PATH = os.getenv("SMARTCLASS_BENCHMARK_OUTPUT", "").strip()


_measurements: list[RunMeasurement] = []
_run_ids: list[str] = []
_lock = threading.Lock()
_prometheus_before = ""


def _read_sse(response: Any):
    event_id = ""
    event_name = "message"
    data: list[str] = []
    for raw in response.iter_lines(decode_unicode=True):
        line = raw or ""
        if not line:
            if data:
                yield event_id, event_name, "\n".join(data)
            event_id, event_name, data = "", "message", []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("id:"):
            event_id = line[3:].strip()
        elif line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())


def _json_payload(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _sample_retained_memory(run_id: str) -> int | None:
    redis_url = os.getenv("SMARTCLASS_BENCHMARK_REDIS_URL", "").strip()
    if not redis_url:
        return None
    from redis import Redis

    environment = os.getenv("DEPLOYMENT_ENVIRONMENT", "local")
    prefix = os.getenv("REDIS_KEY_PREFIX", "sc")
    keys = chat_run_redis_keys(run_id, prefix=prefix, environment=environment)
    client = Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
    try:
        return sum(int(client.memory_usage(key) or 0) for key in asdict(keys).values())
    finally:
        client.close()


@events.test_start.add_listener
def on_test_start(environment: Environment, **_: Any) -> None:
    global _prometheus_before
    with _lock:
        _measurements.clear()
        _run_ids.clear()
    try:
        _prometheus_before = requests.get(f"{environment.host}/metrics", timeout=5).text
    except requests.RequestException:
        _prometheus_before = ""


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **_: Any) -> None:
    try:
        prometheus_after = requests.get(f"{environment.host}/metrics", timeout=5).text
    except requests.RequestException:
        prometheus_after = ""
    with _lock:
        measurements = list(_measurements)
    report = {
        "schema_version": "1.0",
        "benchmark": "redis-chat-run-load",
        "run_mode": "live-http-sse",
        "timestamp": datetime.now(UTC).isoformat(),
        "metrics": aggregate_chat_run_load(measurements, _prometheus_before, prometheus_after),
    }
    if OUTPUT_PATH:
        output = Path(OUTPUT_PATH).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class RedisChatRunUser(HttpUser):
    wait_time = between(0.1, 0.3)

    def on_start(self) -> None:
        self.token = os.getenv("SMARTCLASS_BENCHMARK_TOKEN", "").strip() or self._login()
        plan_id = int(os.getenv("SMARTCLASS_BENCHMARK_PLAN_ID", "0"))
        if not self.token or not plan_id:
            raise StopUser()
        response = self.client.put(
            "/api/session",
            json={"name": "Redis chat-run benchmark", "plan_id": plan_id},
            headers=self._headers(),
            name="[setup]/api/session",
        )
        self.thread_id = str(_json_payload(response).get("thread_id") or "")
        if not self.thread_id:
            raise StopUser()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _login(self) -> str:
        response = self.client.post(
            "/api/auth/login",
            json={
                "username": os.getenv("SMARTCLASS_BENCHMARK_USERNAME", ""),
                "password": os.getenv("SMARTCLASS_BENCHMARK_PASSWORD", ""),
            },
            name="[setup]/api/auth/login",
        )
        return str(_json_payload(response).get("access_token") or "")

    @task
    def durable_chat_run(self) -> None:
        created = self.client.post(
            "/api/chat/runs",
            json={"thread_id": self.thread_id, "message": PROMPT},
            headers=self._headers(),
            name="/api/chat/runs",
        )
        if created.status_code != 202:
            return
        run_id = str(_json_payload(created).get("run_id") or "")
        if not run_id:
            return

        unique_sequences: set[int] = set()
        token_events = 0
        sse_connections = 0
        cursor = 0
        replay_latency_ms: float | None = None

        first = self.client.get(
            f"/api/chat/runs/{run_id}/events?after_sequence=0",
            headers=self._headers(),
            stream=True,
            name="/api/chat/runs/:id/events",
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        )
        sse_connections += 1
        for event_id, event_name, _data in _read_sse(first):
            if event_id.isdigit():
                cursor = int(event_id)
                unique_sequences.add(cursor)
            if event_name == "token":
                token_events += 1
                break
        first.close()

        replay_cursor = max(cursor - 1, 0)
        replay_started = time.perf_counter()
        second = self.client.get(
            f"/api/chat/runs/{run_id}/events?after_sequence={replay_cursor}",
            headers=self._headers(),
            stream=True,
            name="/api/chat/runs/:id/events",
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        )
        sse_connections += 1
        for event_id, event_name, _data in _read_sse(second):
            if replay_latency_ms is None:
                replay_latency_ms = (time.perf_counter() - replay_started) * 1000
            if event_id.isdigit():
                unique_sequences.add(int(event_id))
            if event_name == "token":
                token_events += 1
            if event_name == "done":
                break
        second.close()

        measurement = RunMeasurement(
            event_count=len(unique_sequences),
            token_event_count=token_events,
            sse_connection_count=sse_connections,
            replay_latency_ms=replay_latency_ms,
            retained_memory_bytes=_sample_retained_memory(run_id),
        )
        with _lock:
            _measurements.append(measurement)
            _run_ids.append(run_id)


__all__ = ["RedisChatRunUser"]

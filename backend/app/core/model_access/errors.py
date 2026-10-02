"""Value-free diagnostics and a single bounded logical-request budget."""

import asyncio
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import wraps

import httpx

from .schemas import ConfigError


class ModelAccessError(RuntimeError):
    def __init__(self, category: str, *, retry_after: float = 0):
        self.category = category
        self.retry_after = retry_after
        super().__init__(f"Model request failed ({category})")


def classify(exc: BaseException) -> str:
    if isinstance(exc, ModelAccessError):
        return exc.category
    if isinstance(exc, ConfigError):
        return "capability_error"
    if isinstance(exc, asyncio.CancelledError):
        return "cancelled"
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict) and error.get("code") in {"context_length_exceeded", "context_window_exceeded"}:
            return "context_limit"
    if exc.__cause__ is not None and type(exc).__module__.startswith("langchain_google_genai"):
        return classify(exc.__cause__)
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code == 401:
        return "authentication_error"
    if code == 403:
        return "permission_error"
    if code == 429:
        return "rate_limit"
    if isinstance(code, int) and code >= 500:
        return "server_error"
    if code in {400, 404, 422}:
        return "capability_error"
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)) or "timeout" in type(exc).__name__.lower():
        return "timeout"
    if isinstance(exc, (httpx.TransportError, ConnectionError)) or "connection" in type(exc).__name__.lower():
        return "network_error"
    if isinstance(exc, ValueError):
        return "validation_error"
    return "model_error"


def safe_error(exc: BaseException) -> str:
    return f"Model request failed ({classify(exc)})"


def normalized_error(exc: Exception) -> ModelAccessError:
    if exc.__cause__ is not None and type(exc).__module__.startswith("langchain_google_genai"):
        return normalized_error(exc.__cause__)
    delay = 0.0
    headers = getattr(getattr(exc, "response", None), "headers", {}) or {}
    value = headers.get("retry-after")
    if value:
        try:
            delay = max(0, float(value))
        except ValueError:
            try:
                delay = max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError):
                pass
    return ModelAccessError(classify(exc), retry_after=delay)


@dataclass
class RequestBudget:
    remaining: int = 2
    deadline: float = 0

    def __post_init__(self):
        if not self.deadline:
            self.deadline = time.monotonic() + 60

    def take(self):
        if self.remaining <= 0 or self.seconds <= 0:
            raise ModelAccessError("budget_exhausted")
        self.remaining -= 1

    @property
    def seconds(self):
        return max(0, self.deadline - time.monotonic())

    def delay(self, error):
        if error.category not in {"rate_limit", "server_error", "network_error", "timeout"} or self.remaining <= 0:
            return None
        delay = max(error.retry_after, 0.1)
        return delay if delay < self.seconds else None


_budget = ContextVar("model_request_budget", default=None)


@contextmanager
def request_budget(seconds=60):
    existing = _budget.get()
    if existing is not None:
        yield existing
        return
    token = _budget.set(RequestBudget(deadline=time.monotonic() + seconds))
    try:
        yield _budget.get()
    finally:
        _budget.reset(token)


def bounded_request(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        with request_budget():
            return await function(*args, **kwargs)

    return wrapped


def fallback_allowed(exc):
    return classify(exc) not in {
        "authentication_error",
        "permission_error",
        "capability_error",
        "budget_exhausted",
        "cancelled",
    }

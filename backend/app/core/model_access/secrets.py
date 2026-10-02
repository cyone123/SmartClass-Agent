from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Mapping

from .schemas import ConfigError


class SecretResolver:
    def __init__(self, environ: Mapping[str, str] | None = None):
        self.environ = environ if environ is not None else os.environ
        self._salt = os.urandom(32)

    def resolve(self, reference: str) -> tuple[str, str]:
        value = self.environ.get(reference.removeprefix("env:"), "")
        if not reference.startswith("env:") or not value.strip():
            raise ConfigError("required credential reference is unavailable")
        generation = hmac.new(self._salt, value.encode(), hashlib.sha256).hexdigest()
        return value, generation

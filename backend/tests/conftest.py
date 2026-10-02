from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("MODEL", "test-model")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("BASE_URL", "https://example.com")
os.environ.setdefault("STRUCTURED_MODEL", "test-model")
os.environ.setdefault("STRUCTURED_API_KEY", "test-key")
os.environ.setdefault("STRUCTURED_BASE_URL", "https://example.com")
os.environ.setdefault("SMALL_MODEL", "test-model")
os.environ.setdefault("SMALL_API_KEY", "test-key")
os.environ.setdefault("SMALL_BASE_URL", "https://example.com")
os.environ.setdefault("STRUCTURED_FAST_MODEL", "test-fast-model")
os.environ.setdefault("STRUCTURED_FAST_API_KEY", "test-key")
os.environ.setdefault("STRUCTURED_FAST_BASE_URL", "https://example.com")
os.environ.setdefault("STRUCTURED_FALLBACK_ENABLED", "true")
os.environ.setdefault("STT_MODEL", "test-stt-model")
os.environ.setdefault("STT_API_KEY", "test-key")
os.environ.setdefault("STT_BASE_URL", "https://example.com")
os.environ.setdefault("EMBEDDINGS_MODEL", "test-embeddings-model")
os.environ.setdefault("EMBEDDINGS_API_KEY", "test-key")
os.environ.setdefault("EMBEDDINGS_BASE_URL", "https://example.com")
# 测试必须与本机部署环境隔离：强制本地存储后端，避免读取根目录 .env 的 MinIO 配置
os.environ.setdefault("STORAGE_BACKEND", "local")
for proxy_key in (
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "NO_PROXY",
    "no_proxy",
):
    os.environ.pop(proxy_key, None)


@pytest.fixture
def tmp_path() -> Path:
    path = BACKEND_ROOT / "storage" / "pytest_tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

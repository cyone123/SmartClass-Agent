import os
from pathlib import Path
from urllib.parse import quote, urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    return value


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = get_env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: int) -> int:
    value = get_env(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _get_float_env(name: str, default: float) -> float:
    value = get_env(name)
    if value is None or not value.strip():
        return default
    return float(value)


def get_db_uri() -> str:
    database_url = get_env("DATABASE_URL") or get_env("POSTGRES_URL")
    if database_url:
        return database_url

    raw_host = get_env("DB_HOST", "localhost") or "localhost"
    parsed = urlparse(raw_host if "://" in raw_host else f"//{raw_host}")
    host = parsed.hostname or raw_host.split(":")[0]
    port = parsed.port or int(get_env("DB_PORT", "5432") or "5432")
    database = get_env("DB_NAME") or get_env("POSTGRES_DB") or "postgres"
    user = quote(get_env("DB_USER", "postgres") or "postgres")
    password = quote(get_env("DB_PASSWORD", "") or "")
    sslmode = get_env("DB_SSLMODE")

    conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    if sslmode:
        conn_string = f"{conn_string}?sslmode={sslmode}"
    return conn_string


def get_sqlalchemy_echo() -> bool:
    return _get_bool_env("SQLALCHEMY_ECHO", False)


def get_redis_url() -> str:
    configured = (get_env("REDIS_URL", "redis://127.0.0.1:6379/0") or "").strip()
    parsed = urlparse(configured)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise ValueError("REDIS_URL must be a valid redis:// or rediss:// URL.")
    return configured


def get_redis_key_prefix() -> str:
    configured = (get_env("REDIS_KEY_PREFIX", "sc") or "").strip().strip(":")
    if not configured or any(character in configured for character in "{}\r\n\t "):
        raise ValueError("REDIS_KEY_PREFIX must be non-empty and cannot contain whitespace or braces.")
    return configured


def get_redis_operation_timeout_seconds() -> float:
    value = _get_float_env("REDIS_OPERATION_TIMEOUT_SECONDS", 2.0)
    if value <= 0:
        raise ValueError("REDIS_OPERATION_TIMEOUT_SECONDS must be greater than zero.")
    return value


def get_redis_command_pool_size() -> int:
    value = _get_int_env("REDIS_COMMAND_POOL_SIZE", 20)
    if value < 2:
        raise ValueError("REDIS_COMMAND_POOL_SIZE must be at least 2.")
    return value


def get_redis_reader_pool_size() -> int:
    value = _get_int_env("REDIS_READER_POOL_SIZE", 100)
    if value < 1:
        raise ValueError("REDIS_READER_POOL_SIZE must be at least 1.")
    return value


def get_redis_active_ttl_seconds() -> int:
    value = _get_int_env("REDIS_ACTIVE_TTL_SECONDS", 86400)
    if value < 60:
        raise ValueError("REDIS_ACTIVE_TTL_SECONDS must be at least 60.")
    return value


def get_redis_terminal_retention_seconds() -> int:
    value = _get_int_env("REDIS_TERMINAL_RETENTION_SECONDS", 604800)
    if value < 60:
        raise ValueError("REDIS_TERMINAL_RETENTION_SECONDS must be at least 60.")
    return value


def get_redis_token_batch_interval_ms() -> int:
    value = _get_int_env("REDIS_TOKEN_BATCH_INTERVAL_MS", 40)
    if value < 1:
        raise ValueError("REDIS_TOKEN_BATCH_INTERVAL_MS must be at least 1.")
    return value


def get_redis_token_batch_max_chars() -> int:
    value = _get_int_env("REDIS_TOKEN_BATCH_MAX_CHARS", 1024)
    if value < 1:
        raise ValueError("REDIS_TOKEN_BATCH_MAX_CHARS must be at least 1.")
    return value


def get_redis_read_block_ms() -> int:
    value = _get_int_env("REDIS_READ_BLOCK_MS", 15000)
    if value < 100:
        raise ValueError("REDIS_READ_BLOCK_MS must be at least 100.")
    return value


def get_redis_read_batch_size() -> int:
    value = _get_int_env("REDIS_READ_BATCH_SIZE", 200)
    if value < 1:
        raise ValueError("REDIS_READ_BATCH_SIZE must be at least 1.")
    return value


def get_redis_append_max_retries() -> int:
    value = _get_int_env("REDIS_APPEND_MAX_RETRIES", 2)
    if value < 0 or value > 10:
        raise ValueError("REDIS_APPEND_MAX_RETRIES must be between 0 and 10.")
    return value


def get_memory_reflection_worker_enabled() -> bool:
    return _get_bool_env("MEMORY_REFLECTION_WORKER_ENABLED", True)


def get_memory_reflection_shadow_mode() -> bool:
    return _get_bool_env("MEMORY_REFLECTION_SHADOW_MODE", False)


def get_memory_reflection_poll_seconds() -> float:
    value = _get_float_env("MEMORY_REFLECTION_POLL_SECONDS", 1.0)
    if value <= 0:
        raise ValueError("MEMORY_REFLECTION_POLL_SECONDS must be greater than zero.")
    return value


def get_memory_reflection_profile_snapshot_max_chars() -> int:
    return max(256, _get_int_env("MEMORY_REFLECTION_PROFILE_SNAPSHOT_MAX_CHARS", 4000))


def get_memory_reflection_experience_snapshot_max_chars() -> int:
    return max(1024, _get_int_env("MEMORY_REFLECTION_EXPERIENCE_SNAPSHOT_MAX_CHARS", 16000))


def get_memory_reflection_evaluation_timeout_seconds() -> float:
    value = _get_float_env("MEMORY_REFLECTION_EVALUATION_TIMEOUT_SECONDS", 30.0)
    if value <= 0:
        raise ValueError("MEMORY_REFLECTION_EVALUATION_TIMEOUT_SECONDS must be greater than zero.")
    return value


def get_memory_reflection_terminal_retention_days() -> int:
    value = _get_int_env("MEMORY_REFLECTION_TERMINAL_RETENTION_DAYS", 30)
    if value < 1:
        raise ValueError("MEMORY_REFLECTION_TERMINAL_RETENTION_DAYS must be at least 1.")
    return value


def _get_bounded_memory_limit(name: str, default: int, *, minimum: int, maximum: int) -> int:
    value = _get_int_env(name, default)
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def get_profile_memory_item_limit() -> int:
    return _get_bounded_memory_limit("PROFILE_MEMORY_ITEM_LIMIT", 100, minimum=1, maximum=1000)


def get_profile_memory_context_max_chars() -> int:
    return _get_bounded_memory_limit("PROFILE_MEMORY_CONTEXT_MAX_CHARS", 6000, minimum=256, maximum=50000)


def get_experience_memory_candidate_limit() -> int:
    return _get_bounded_memory_limit("EXPERIENCE_MEMORY_CANDIDATE_LIMIT", 100, minimum=1, maximum=500)


def get_experience_memory_semantic_enabled() -> bool:
    return _get_bool_env("EXPERIENCE_MEMORY_SEMANTIC_ENABLED", True)


def get_experience_memory_embedding_dimensions() -> int:
    # pgvector's HNSW `halfvec` index supports at most 4,000 dimensions.
    return _get_bounded_memory_limit("EXPERIENCE_MEMORY_EMBEDDING_DIMENSIONS", 3072, minimum=1, maximum=4000)


def get_experience_memory_index_fields() -> tuple[str, ...]:
    raw = get_env("EXPERIENCE_MEMORY_INDEX_FIELDS", "title,summary,tags") or ""
    fields = tuple(dict.fromkeys(part.strip() for part in raw.split(",") if part.strip()))
    allowed = {"title", "summary", "tags"}
    if not fields or any(field not in allowed for field in fields):
        raise ValueError("EXPERIENCE_MEMORY_INDEX_FIELDS must contain only title, summary, and tags.")
    return fields


def get_experience_memory_semantic_candidate_limit() -> int:
    return _get_bounded_memory_limit("EXPERIENCE_MEMORY_SEMANTIC_CANDIDATE_LIMIT", 12, minimum=1, maximum=100)


def get_experience_memory_semantic_confidence_threshold() -> float:
    value = _get_float_env("EXPERIENCE_MEMORY_SEMANTIC_CONFIDENCE_THRESHOLD", 0.82)
    if value < -1 or value > 1:
        raise ValueError("EXPERIENCE_MEMORY_SEMANTIC_CONFIDENCE_THRESHOLD must be between -1 and 1.")
    return value


def get_experience_memory_selector_summary_max_chars() -> int:
    return _get_bounded_memory_limit("EXPERIENCE_MEMORY_SELECTOR_SUMMARY_MAX_CHARS", 8000, minimum=512, maximum=50000)


def get_experience_memory_item_limit() -> int:
    return _get_bounded_memory_limit("EXPERIENCE_MEMORY_ITEM_LIMIT", 3, minimum=1, maximum=10)


def get_experience_memory_query_max_chars() -> int:
    return _get_bounded_memory_limit("EXPERIENCE_MEMORY_QUERY_MAX_CHARS", 4000, minimum=128, maximum=20000)


def get_experience_memory_context_max_chars() -> int:
    return _get_bounded_memory_limit("EXPERIENCE_MEMORY_CONTEXT_MAX_CHARS", 6000, minimum=256, maximum=50000)


def get_experience_memory_tool_output_max_chars() -> int:
    return _get_bounded_memory_limit("EXPERIENCE_MEMORY_TOOL_OUTPUT_MAX_CHARS", 2000, minimum=128, maximum=10000)


def get_teaching_intake_context_max_chars() -> int:
    return _get_bounded_memory_limit("TEACHING_INTAKE_CONTEXT_MAX_CHARS", 12000, minimum=1000, maximum=50000)


def get_teaching_intake_max_turns() -> int:
    return _get_bounded_memory_limit("TEACHING_INTAKE_MAX_TURNS", 8, minimum=1, maximum=20)


def get_backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_skills_root() -> Path:
    configured = get_env("SKILLS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return get_backend_root() / "skills"


def get_file_storage_root() -> Path:
    configured = get_env("FILE_STORAGE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return get_backend_root() / "storage"


def get_observability_enabled() -> bool:
    return _get_bool_env("OBSERVABILITY_ENABLED", True)


def get_observability_log_level() -> str:
    return (get_env("OBSERVABILITY_LOG_LEVEL", "info") or "info").strip().lower()


def get_observability_trace_jsonl_enabled() -> bool:
    return _get_bool_env("OBSERVABILITY_TRACE_JSONL_ENABLED", False)


def get_observability_trace_jsonl_dir() -> Path:
    storage_root = get_file_storage_root().resolve()
    configured = get_env("OBSERVABILITY_TRACE_JSONL_DIR")
    if configured:
        candidate = Path(configured).expanduser().resolve()
    else:
        candidate = storage_root / "observability" / "traces"

    try:
        candidate.relative_to(storage_root)
    except ValueError:
        return storage_root / "observability" / "traces"
    return candidate


def get_observability_max_field_chars() -> int:
    return _get_int_env("OBSERVABILITY_MAX_FIELD_CHARS", 1000)


def get_observability_max_jsonl_bytes_per_event() -> int:
    return _get_int_env("OBSERVABILITY_MAX_JSONL_BYTES_PER_EVENT", 20000)


def get_otel_enabled() -> bool:
    return _get_bool_env("OTEL_ENABLED", False)


def get_otel_service_name() -> str:
    return (get_env("OTEL_SERVICE_NAME", "smartclass-backend") or "smartclass-backend").strip()


def get_otel_environment() -> str:
    return (
        get_env("OTEL_RESOURCE_ATTRIBUTES_DEPLOYMENT_ENVIRONMENT")
        or get_env("DEPLOYMENT_ENVIRONMENT")
        or get_env("ENVIRONMENT")
        or "local"
    ).strip()


def get_otel_endpoint() -> str | None:
    configured = (
        get_env("OTEL_EXPORTER_OTLP_ENDPOINT")
        or get_env("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or get_env("OTEL_OTLP_ENDPOINT")
    )
    if configured is None:
        return None
    normalized = configured.strip().rstrip("/")
    return normalized or None


def get_otel_protocol() -> str:
    return (get_env("OTEL_EXPORTER_OTLP_PROTOCOL") or get_env("OTEL_OTLP_PROTOCOL") or "http/protobuf").strip().lower()


def get_otel_sample_ratio() -> float:
    value = _get_float_env("OTEL_TRACES_SAMPLER_ARG", 1.0)
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def get_otel_insecure() -> bool:
    return _get_bool_env("OTEL_EXPORTER_OTLP_INSECURE", True)


def get_prometheus_enabled() -> bool:
    return _get_bool_env("PROMETHEUS_ENABLED", False)


def get_prometheus_metrics_path() -> str:
    configured = (get_env("PROMETHEUS_METRICS_PATH", "/metrics") or "/metrics").strip()
    if not configured.startswith("/"):
        configured = f"/{configured}"
    return configured


def get_prometheus_histogram_buckets() -> tuple[float, ...]:
    raw = get_env("PROMETHEUS_HISTOGRAM_BUCKETS")
    if raw:
        buckets = tuple(sorted(float(item.strip()) for item in raw.split(",") if item.strip()))
        if buckets:
            return buckets
    return (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)


def get_prometheus_export_mode() -> str:
    return (get_env("PROMETHEUS_EXPORT_MODE", "endpoint") or "endpoint").strip().lower()


def get_context_compression_enabled() -> bool:
    return _get_bool_env("CONTEXT_COMPRESSION_ENABLED", False)


def get_context_compression_model() -> str | None:
    return get_env("CONTEXT_COMPRESSION_MODEL")


def get_context_compression_api_key() -> str | None:
    return get_env("CONTEXT_COMPRESSION_API_KEY")


def get_context_compression_base_url() -> str | None:
    return get_env("CONTEXT_COMPRESSION_BASE_URL")


def get_context_compression_timeout_seconds() -> float | None:
    timeout_ms = _get_int_env("CONTEXT_COMPRESSION_TIMEOUT_MS", 30000)
    if timeout_ms <= 0:
        return None
    return timeout_ms / 1000


def get_context_compression_trigger_tokens() -> int:
    return _get_int_env("CONTEXT_COMPRESSION_TRIGGER_TOKENS", 24000)


def get_context_compression_keep_recent_turns() -> int:
    return max(1, _get_int_env("CONTEXT_COMPRESSION_KEEP_RECENT_TURNS", 6))


def get_context_compression_max_output_tokens() -> int:
    return max(256, _get_int_env("CONTEXT_COMPRESSION_MAX_OUTPUT_TOKENS", 3000))


def get_context_compression_max_preface_chars() -> int:
    return max(1000, _get_int_env("CONTEXT_COMPRESSION_MAX_PREFACE_CHARS", 6000))


def get_public_api_base_url() -> str | None:
    configured = get_env("PUBLIC_API_BASE_URL")
    if configured is None:
        return None

    normalized = configured.strip().rstrip("/")
    return normalized or None


def get_storage_backend() -> str:
    return (get_env("STORAGE_BACKEND", "local") or "local").strip().lower()


def get_minio_endpoint() -> str | None:
    configured = get_env("MINIO_ENDPOINT")
    if configured is None:
        return None
    return configured.strip() or None


def get_minio_bucket() -> str | None:
    configured = get_env("MINIO_BUCKET")
    if configured is None:
        return None
    return configured.strip() or None


def get_minio_access_key() -> str | None:
    configured = get_env("MINIO_ACCESS_KEY")
    if configured is None:
        return None
    return configured.strip() or None


def get_minio_secret_key() -> str | None:
    configured = get_env("MINIO_SECRET_KEY")
    if configured is None:
        return None
    return configured.strip() or None


def get_minio_region() -> str | None:
    configured = get_env("MINIO_REGION")
    if configured is None:
        return None
    return configured.strip() or None


def get_minio_secure() -> bool:
    return _get_bool_env("MINIO_SECURE", False)


def get_storage_presigned_url_ttl_seconds() -> int:
    return _get_int_env("STORAGE_PRESIGNED_URL_TTL_SECONDS", 900)


def get_storage_download_mode() -> str:
    return (get_env("STORAGE_DOWNLOAD_MODE", "proxy") or "proxy").strip().lower()


def get_file_upload_max_size_bytes() -> int:
    value = get_env("FILE_UPLOAD_MAX_SIZE_BYTES", "20971520") or "20971520"
    return int(value)


def _parse_allowed_extensions(raw: str | None, default: str) -> set[str]:
    value = raw if raw is not None else default
    return {extension.strip().lower() for extension in value.split(",") if extension.strip()}


def get_allowed_knowledge_upload_extensions() -> set[str]:
    return _parse_allowed_extensions(
        get_env("KNOWLEDGE_FILE_ALLOWED_EXTENSIONS"),
        ".docx,.pdf,.txt,.md,.markdown,.csv,.json",
    )


def get_allowed_attachment_upload_extensions() -> set[str]:
    return _parse_allowed_extensions(
        get_env("ATTACHMENT_FILE_ALLOWED_EXTENSIONS"),
        ".docx,.pdf,.mp4",
    )


def get_allowed_voice_upload_extensions() -> set[str]:
    return _parse_allowed_extensions(
        get_env("VOICE_FILE_ALLOWED_EXTENSIONS"),
        ".webm,.wav,.mp3,.m4a,.mp4,.ogg",
    )


def get_allowed_upload_extensions() -> set[str]:
    return get_allowed_knowledge_upload_extensions()


def get_stt_model() -> str | None:
    return get_env("STT_MODEL") or get_env("MODEL")


def get_stt_base_url() -> str | None:
    return get_env("STT_BASE_URL") or get_env("BASE_URL")


def get_stt_api_key() -> str | None:
    return get_env("STT_API_KEY") or get_env("API_KEY")


def get_stt_language() -> str | None:
    configured = get_env("STT_LANGUAGE")
    if configured is None:
        return None
    normalized = configured.strip()
    return normalized or None


def get_video_ffmpeg_bin() -> str:
    return (get_env("VIDEO_FFMPEG_BIN", "ffmpeg") or "ffmpeg").strip() or "ffmpeg"


def get_video_vision_model() -> str | None:
    return get_env("VIDEO_VISION_MODEL") or get_env("MODEL")


def get_video_vision_base_url() -> str | None:
    return get_env("VIDEO_VISION_BASE_URL") or get_env("BASE_URL")


def get_video_vision_api_key() -> str | None:
    return get_env("VIDEO_VISION_API_KEY") or get_env("API_KEY")


def get_workspace_execution_backend() -> str:
    return (get_env("WORKSPACE_EXECUTION_BACKEND", "local") or "local").strip().lower()


def get_daytona_api_key() -> str | None:
    return get_env("DAYTONA_API_KEY")


def get_daytona_api_url() -> str | None:
    return get_env("DAYTONA_API_URL")


def get_daytona_target() -> str | None:
    return get_env("DAYTONA_TARGET")


def get_daytona_snapshot() -> str | None:
    return get_env("DAYTONA_SNAPSHOT")


def get_daytona_image() -> str | None:
    return get_env("DAYTONA_IMAGE")


def get_daytona_cleanup_policy() -> str:
    return (get_env("DAYTONA_CLEANUP_POLICY", "delete") or "delete").strip().lower()


def get_daytona_network_block_all() -> bool:
    return _get_bool_env("DAYTONA_NETWORK_BLOCK_ALL", True)


def get_daytona_network_allow_list() -> str | None:
    configured = get_env("DAYTONA_NETWORK_ALLOW_LIST")
    if configured is None:
        return None
    normalized = configured.strip()
    return normalized or None


def get_daytona_auto_stop_interval_minutes() -> int:
    return _get_int_env("DAYTONA_AUTO_STOP_INTERVAL_MINUTES", 15)


def get_daytona_auto_archive_interval_minutes() -> int:
    return _get_int_env("DAYTONA_AUTO_ARCHIVE_INTERVAL_MINUTES", 60 * 24)


def get_daytona_auto_delete_interval_minutes() -> int:
    return _get_int_env("DAYTONA_AUTO_DELETE_INTERVAL_MINUTES", 60 * 24 * 7)


def get_daytona_create_timeout_seconds() -> int:
    return _get_int_env("DAYTONA_CREATE_TIMEOUT_SECONDS", 60)


def get_daytona_execution_timeout_seconds() -> int:
    return _get_int_env("DAYTONA_EXECUTION_TIMEOUT_SECONDS", 120)


def get_daytona_file_sync_timeout_seconds() -> int:
    return _get_int_env("DAYTONA_FILE_SYNC_TIMEOUT_SECONDS", 30 * 60)


def get_daytona_remote_root() -> str:
    return (get_env("DAYTONA_REMOTE_ROOT", "/workspace/smartclass") or "/workspace/smartclass").strip()

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.evals.reporting import (
    BaselinePromotionError,
    build_sanitized_summary,
    promote_baseline,
)

FIXTURES = Path(__file__).parent / "fixtures" / "reports"


def test_summary_uses_aggregate_allowlist() -> None:
    raw = json.loads((FIXTURES / "passing.json").read_text(encoding="utf-8"))
    raw.update(
        {
            "prompt": "PRIVATE PROMPT",
            "completion": "PRIVATE COMPLETION",
            "memory_body": "PRIVATE MEMORY",
            "object_key": "users/1/private.docx",
            "error_message": (
                "Bearer abc.def.ghi "
                "https://example.test/file?access_token=secret&X-Amz-Signature=sig "
                "D:\\Learn\\langchain\\demo\\backend\\storage\\private.docx"
            ),
            "results": [{"actual_output": {"attachment": "PRIVATE ATTACHMENT"}}],
            "model": {
                "configuration_version": "v1:safe",
                "roles": {
                    "main": {
                        "provider": "openrouter",
                        "protocol": "openai_chat",
                        "model": "vendor/model",
                        "thinking": "on",
                        "actual_upstream": "unknown",
                        "provider_routing": {"allow_fallbacks": False, "require_parameters": True},
                        "endpoint": "https://private.example/v1",
                        "credential": "env:PRIVATE_KEY",
                        "prompt": "PRIVATE MODEL PROMPT",
                    }
                },
            },
        }
    )
    serialized = json.dumps(build_sanitized_summary(raw), ensure_ascii=False)
    for forbidden in (
        "PRIVATE PROMPT",
        "PRIVATE COMPLETION",
        "PRIVATE MEMORY",
        "PRIVATE ATTACHMENT",
        "abc.def.ghi",
        "access_token",
        "X-Amz-Signature",
        "users/1/private.docx",
        "D:\\Learn",
        "private.example",
        "PRIVATE_KEY",
        "PRIVATE MODEL PROMPT",
    ):
        assert forbidden not in serialized
    model = build_sanitized_summary(raw)["model"]
    assert model["configuration_version"] == "v1:safe"
    assert model["roles"]["main"]["thinking"] == "on"
    assert model["roles"]["main"]["provider_routing"]["allow_fallbacks"] is False


def test_promote_baseline_writes_three_safe_files(tmp_path: Path) -> None:
    target = promote_baseline(
        FIXTURES / "passing.json",
        baseline_id="stage0-smoke",
        benchmarks_root=tmp_path,
    )
    assert {path.name for path in target.iterdir()} == {
        "manifest.yaml",
        "summary.json",
        "report.md",
    }
    assert not (tmp_path / "results").exists()


def test_duplicate_baseline_is_immutable_by_default(tmp_path: Path) -> None:
    promote_baseline(
        FIXTURES / "passing.json",
        baseline_id="stage0-smoke",
        benchmarks_root=tmp_path,
    )
    with pytest.raises(BaselinePromotionError, match="already exists"):
        promote_baseline(
            FIXTURES / "passing.json",
            baseline_id="stage0-smoke",
            benchmarks_root=tmp_path,
        )


def test_legacy_report_cannot_be_promoted(tmp_path: Path) -> None:
    with pytest.raises(BaselinePromotionError, match="Legacy"):
        promote_baseline(
            FIXTURES / "legacy.json",
            baseline_id="legacy-report",
            benchmarks_root=tmp_path,
        )

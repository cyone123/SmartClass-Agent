import json

import pytest

from tests.provider_smoke import run, run_provider


@pytest.mark.asyncio
async def test_missing_credentials_are_unverified_and_fail_gate(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr("tests.provider_smoke._environment", lambda: {})
    output = tmp_path / "report.json"
    report, passed = await run(["openrouter"], output)
    assert not passed
    assert report["summary"] == {"passed": 0, "failed": 0, "unverified": 3}
    assert {item["status"] for item in report["results"]} == {"unverified"}
    serialized = output.read_text(encoding="utf-8")
    assert "credential_or_model_missing" in serialized
    assert "api_key" not in serialized.lower() and "endpoint" not in serialized.lower()


@pytest.mark.asyncio
async def test_declared_optional_checks_are_reported_individually():
    results = await run_provider(
        "zhipu",
        {"ZHIPU_MODEL": "glm-test", "ZHIPU_SMOKE_CAPABILITIES": "structured,thinking,vision"},
    )
    assert [result.capability for result in results] == [
        "text",
        "stream",
        "tools",
        "structured",
        "thinking",
        "vision",
    ]
    assert all(result.status == "unverified" for result in results)
    assert "glm-test" in json.dumps([result.__dict__ for result in results])

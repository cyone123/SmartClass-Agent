"""Stage 5 cross-layer contracts; deterministic and offline."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.core import agent, graph, llm
from app.core.model_access.config_repository import FileConfigRepository
from app.services import artifact_service


def test_business_model_entrypoints_select_explicit_roles(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    def resolve(role: str, *, streaming: bool = False):
        calls.append((role, streaming))
        return role

    monkeypatch.setattr(llm, "get_role_model", resolve)

    assert llm.get_model(streaming=True) == "main"
    assert llm.get_structured_output_model() == "structured"
    assert llm.get_small_model() == "small"
    assert llm.get_structured_fast_model() == "structured_fast"
    assert llm.get_memory_model() == "memory"
    assert llm.get_context_compression_llm() == "compression"
    assert calls == [
        ("main", True),
        ("structured", False),
        ("small", False),
        ("structured_fast", False),
        ("memory", False),
        ("compression", False),
    ]


def test_graph_keeps_approval_and_three_artifact_fan_in_boundaries() -> None:
    source = inspect.getsource(graph.build_agent_graph)
    for node in (
        graph.METADATA_REVIEW_INTERRUPT_NODE,
        graph.TEACHING_PLAN_REVIEW_INTERRUPT_NODE,
        "artifact_revision_clarification_interrupt_node",
    ):
        assert node in source
    for node in (
        "ppt_generate_node",
        "docx_generate_node",
        "html_game_generate_node",
        "ppt_revision_node",
        "docx_revision_node",
        "html_game_revision_node",
    ):
        assert f'add_edge("{node}", "artifact_fan_in_node")' in source


def test_artifact_runtime_keeps_workspace_and_storage_service_boundaries() -> None:
    runtime_source = inspect.getsource(agent.AgentRuntime.__init__)
    storage_source = inspect.getsource(artifact_service)
    assert "WorkspaceToolset()" in runtime_source
    assert "get_storage_service().put_file" in storage_source
    assert "get_storage_service().materialize_temp_file" in storage_source
    assert "Path(artifact.storage_path)" not in storage_source


def test_root_yaml_loads_by_windows_relative_path_and_compose_mount_is_read_only() -> None:
    workspace = Path(__file__).resolve().parents[2]
    snapshot = FileConfigRepository(
        "model-config.example.yaml",
        root=workspace,
        environ={"API_KEY": "test-only"},
    ).load()
    assert snapshot.roles["main"].model == "teaching"
    assert snapshot.connections["primary"].protocol == "openai_chat"

    compose = (workspace / "docker-compose.yml").read_text(encoding="utf-8")
    assert "./model-config.example.yaml:/app/config/model-config.yaml:ro" in compose
    assert "MODEL_CONFIG_PATH: ${MODEL_CONFIG_PATH:-}" in compose

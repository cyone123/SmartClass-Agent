"""Run acceptance envelopes and checkpoint selection; internal server state only."""

from __future__ import annotations

from uuid import uuid4

from .factory import current_snapshot
from .schemas import ConfigError, ResolvedModelConfigSnapshot, Schema, restore_snapshot


class RunModelEnvelope(Schema):
    version: int = 1
    current: ResolvedModelConfigSnapshot
    workflow: ResolvedModelConfigSnapshot | None = None
    workflow_id: str | None = None
    legacy_snapshot_adopted: bool = False

    def selected(self) -> ResolvedModelConfigSnapshot:
        return self.workflow or self.current


def restore_envelope(data: dict) -> RunModelEnvelope:
    envelope = RunModelEnvelope.model_validate(data)
    if envelope.version != 1:
        raise ConfigError("unsupported run model envelope version")
    restore_snapshot(envelope.current.model_dump())
    if envelope.workflow:
        restore_snapshot(envelope.workflow.model_dump())
    return envelope


def capture_envelope(values: dict | None = None, *, legacy: bool = False) -> RunModelEnvelope:
    values = values or {}
    active = values.get("model_workflow_active", values.get("teaching_task_active", False))
    previous = values.get("model_config_snapshot") if active else None
    current = current_snapshot()
    return RunModelEnvelope(
        current=current,
        workflow=restore_snapshot(previous) if previous else (current if active else None),
        workflow_id=values.get("model_workflow_id") if previous else (uuid4().hex if active else None),
        legacy_snapshot_adopted=legacy or bool(active and (not previous or values.get("legacy_snapshot_adopted"))),
    )


def entry_update(envelope: RunModelEnvelope) -> dict:
    return {
        "model_run_envelope": envelope.model_dump(mode="json"),
        "model_config_snapshot": envelope.selected().model_dump(mode="json"),
        "model_workflow_id": envelope.workflow_id,
        "model_workflow_active": envelope.workflow is not None,
        "legacy_snapshot_adopted": envelope.legacy_snapshot_adopted,
    }


def begin_workflow(state: dict) -> dict:
    raw = state.get("model_run_envelope")
    snapshot = restore_envelope(raw).current if raw else current_snapshot()
    return {
        "model_config_snapshot": snapshot.model_dump(mode="json"),
        "model_workflow_id": uuid4().hex,
        "model_workflow_active": True,
        "model_config_selection": "accepted_current",
    }

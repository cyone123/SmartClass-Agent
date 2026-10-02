"""Persist admissions separately so writing config never advances a paused business graph."""

from __future__ import annotations

from hashlib import sha256
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .schemas import ConfigError
from .workflow import capture_envelope, restore_envelope


class AdmissionState(TypedDict):
    run_id: str
    envelope: dict


def admission_graph(checkpointer):
    if not checkpointer:
        raise ConfigError("model admission requires durable checkpoint storage")
    builder = StateGraph(AdmissionState)
    builder.add_node("persist", lambda state: {})
    builder.add_edge(START, "persist")
    builder.add_edge("persist", END)
    return builder.compile(checkpointer=checkpointer)


def admission_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": "__model_admission__:" + sha256(thread_id.encode()).hexdigest()}}


async def recover_legacy_workflow(graph, thread_id: str, values: dict) -> dict:
    if values.get("model_workflow_active") and not values.get("model_config_snapshot"):
        saved = await graph.aget_state(admission_config(thread_id))
        if saved.values.get("envelope"):
            previous = restore_envelope(saved.values["envelope"])
            if previous.workflow is None:
                return values
            return {
                **values,
                "model_config_snapshot": previous.selected().model_dump(mode="json"),
                "model_workflow_id": previous.workflow_id,
                "legacy_snapshot_adopted": True,
            }
    return values


async def persist_admission(graph, thread_id: str, run_id: str, values: dict, supplied: dict | None = None):
    config = admission_config(thread_id)
    saved = await graph.aget_state(config)
    if saved.values.get("run_id") == run_id:
        return restore_envelope(saved.values["envelope"])
    envelope = restore_envelope(supplied) if supplied else capture_envelope(values)
    await graph.aupdate_state(
        config, {"run_id": run_id, "envelope": envelope.model_dump(mode="json")}, as_node="persist"
    )
    return envelope

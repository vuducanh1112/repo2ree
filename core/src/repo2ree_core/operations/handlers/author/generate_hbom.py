"""Handler for the generate_hbom operation.

Profiles the workbench container's hardware and merges the result into
/ree/.workspace.json under reeIntent.hardware_description.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.hbom.generate_hbom import generate_hbom
from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.steps.author import open_ree_store, patch_ree_intent
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class GenerateHbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hardware_description: dict[str, Any]
    component_counts: dict[str, int]


def handle_generate_hbom(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    opened = open_ree_store(log)
    if isinstance(opened, ActionResult):
        return opened
    _layout, store = opened

    log("system", "info", "profiling hardware")
    try:
        profiled = generate_hbom()
    except Exception as exc:
        log("system", "error", f"hardware profiling failed: {exc}")
        return failed_from_exception(exc, f"hardware profiling failed: {exc}")

    if is_canceled():
        log("system", "warn", "generate_hbom canceled after profiling")
        return ActionResult(status="canceled")

    try:
        existing_hbom = store.read_intent().hardware_description
        merged = HBOM(
            cpus={**profiled.cpus, **existing_hbom.cpus},
            gpus={**profiled.gpus, **existing_hbom.gpus},
            memory={**profiled.memory, **existing_hbom.memory},
            storage={**profiled.storage, **existing_hbom.storage},
            network={**profiled.network, **existing_hbom.network},
            extra_info={**profiled.extra_info, **existing_hbom.extra_info},
        )
        patch_ree_intent(store, {"hardware_description": merged.model_dump(exclude_none=True)})
    except Exception as exc:
        log("system", "error", f"failed to persist hbom: {exc}")
        return failed_from_exception(exc, f"failed to persist hbom: {exc}")

    log("system", "info", "generate_hbom succeeded")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=GenerateHbomOutputs(
            hardware_description=merged.model_dump(exclude_none=True),
            component_counts={
                "cpus": len(merged.cpus),
                "gpus": len(merged.gpus),
                "memory": len(merged.memory),
                "storage": len(merged.storage),
                "network": len(merged.network),
            },
        ).model_dump(),
    )

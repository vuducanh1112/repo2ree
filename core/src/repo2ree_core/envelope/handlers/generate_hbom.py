"""Handler for the generate_hbom operation.

Profiles the workbench container's hardware and merges the result into
/ree/.workspace.json under reeIntent.hardware_description.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.envelope.handlers._common import patch_ree_intent
from repo2ree_core.hbom.generate_hbom import generate_hbom
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment.base import CancelCheck
from repo2ree_protocol.result import ActionResult


def handle_generate_hbom(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "generate_hbom canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    if not store.metadata_exists():
        log("system", "error", "metadata not found — was init-ree run?")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "profiling hardware")
    try:
        profiled = generate_hbom()
    except Exception as exc:
        log("system", "error", f"hardware profiling failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

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
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "generate_hbom succeeded")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs={
            "hardwareDescription": merged.model_dump(exclude_none=True),
            "componentCounts": {
                "cpus": len(merged.cpus),
                "gpus": len(merged.gpus),
                "memory": len(merged.memory),
                "storage": len(merged.storage),
                "network": len(merged.network),
            },
        },
    )

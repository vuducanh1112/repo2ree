"""Observe workbench hardware and commit successful evidence to the REE."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.hbom.generate_hbom import generate_hbom
from repo2ree_core.domain.ree.receipt import ObserveHardwareReceipt, receipt_envelope
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class GenerateHbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: dict[str, Any]
    component_counts: dict[str, int]
    receipt: ObserveHardwareReceipt


def handle_generate_hbom(
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "metadata not found — was init-ree run?")
    try:
        ree = load_ree(layout, store)
        if ree.seal is not None:
            raise ReePreconditionError("a sealed REE cannot observe hardware")
    except ReePreconditionError as exc:
        return ActionResult.failed("precondition", str(exc))
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load REE: {exc}")

    before_revision = revision_of(ree)
    timer = OperationTimer.start()
    log("system", "info", "profiling hardware")
    try:
        observation = generate_hbom()
    except Exception as exc:
        log("system", "error", f"hardware profiling failed: {exc}")
        return failed_from_exception(exc, f"hardware profiling failed: {exc}")
    if is_canceled():
        log("system", "warn", "generate_hbom canceled after profiling")
        return ActionResult(status="canceled")

    timing = timer.finish()
    receipt = ObserveHardwareReceipt(
        **receipt_envelope(run_id, timing),
        observation=observation,
        observer_version="1",
    )
    try:
        save_ree(layout, store, commit_receipt(ree, receipt), expected_revision=before_revision)
    except ReeRevisionConflictError as exc:
        return ActionResult.failed("conflict", str(exc), retryable=True)
    except Exception as exc:
        return failed_from_exception(exc, f"failed to commit hardware observation: {exc}")

    outputs = GenerateHbomOutputs(
        observation=observation.model_dump(exclude_none=True),
        component_counts={
            "cpus": len(observation.cpus),
            "gpus": len(observation.gpus),
            "memory": len(observation.memory),
            "storage": len(observation.storage),
            "network": len(observation.network),
        },
        receipt=receipt,
    )
    log("system", "info", "generate_hbom succeeded")
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))

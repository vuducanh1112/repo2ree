"""The shared shape of an author-side step: preconditions, input slice, receipt.

A step handler is mostly ceremony around one script run — open the REE, digest
what the run is about to consume, run it, write a receipt binding the two, and
report a status that agrees with all three. That ceremony lives here so the
handlers can be about what makes them different.

Nothing here knows its callers, by name or by type: a step that records
something another does not says so with a :class:`RunnableStep` field. Design
rationale: ``docs/engineering/step-lifecycle.md``.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_serializer

from repo2ree_core.digests import Digest, digest_bytes, digest_file_if_exists, digest_output_paths
from repo2ree_core.domain.experiment import Runnable
from repo2ree_core.domain.primitives import ScriptPath, WorkspacePath
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.receipt import (
    ActivationTestReceipt,
    ReceiptEnvelopeFields,
    RunExperimentReceipt,
    RunnableStepFields,
    RunReceipt,
    WorkspaceDrift,
    receipt_envelope,
)
from repo2ree_core.domain.ree.transitions import patch_intent
from repo2ree_core.execution.experiment.run import RunnableRunOutputs, run_runnable
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.path_safety import WORKSPACE_CONTROL_PREFIXES, resolve_within
from repo2ree_core.persistence.directory import UNREADABLE_DOCUMENT, ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.receipts import record_receipt
from repo2ree_core.persistence.repository import load_ree
from repo2ree_core.time_utils import OperationTimer, OperationTiming, format_duration_ms
from repo2ree_core.workspace.drift import check_workspace_drift, declared_output_paths
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult, ActionStatus
from repo2ree_protocol.tracing import ReceiptInputAttrs


def resolve_workspace_path(layout: ReeLayout, rel_path: str) -> Path:
    path = rel_path.strip()
    candidate = resolve_within(layout.workspace, path)
    if candidate is None:
        raise ValueError("Invalid workspace path")
    # Only the leaf segment is guarded: the reserved control prefixes name files
    # (".workspace*", ".upload.*"), never directories, so a parent segment can
    # never collide with them.
    if PurePosixPath(path).name.startswith(WORKSPACE_CONTROL_PREFIXES):
        raise ValueError("Invalid workspace path")
    return candidate


@dataclass(frozen=True)
class StepInputs:
    """The input slice of a workspace-dependent step, collected *before* the
    run so outputs landing in the workspace cannot leak into it."""

    snapshot_digest: Digest | None
    script_digest: Digest | None
    verify_script_digest: Digest | None
    runtime_path: WorkspacePath | None
    declared_runtime_digest: Digest | None
    workspace_drift: WorkspaceDrift


METADATA_MISSING = "metadata not found — was init-ree run?"


def open_ree_store(log: LogSink) -> tuple[ReeLayout, ReeDirectory] | ActionResult:
    """Open the workbench REE store, or the failure to return when it is absent.

    Every handler that touches REE state starts this way, so the guard and the
    message an author sees for "no REE here yet" live in one place. Callers
    ``return`` the ActionResult unchanged, then unpack::

        layout, store = opened
    """
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)
    if not store.sidecar_exists():
        log("system", "error", METADATA_MISSING)
        return ActionResult.failed("precondition", METADATA_MISSING)
    return layout, store


def read_intent_or_none(store: ReeDirectory, *, log: LogSink) -> ReeIntent | None:
    """The intent, or None when there is no readable metadata.

    For the read-only paths that must still answer when a REE is half-built
    (inference, step inputs) rather than fail the command. An unreadable sidecar
    is logged, because what follows records "nothing declared" either way and
    only the log distinguishes the two.
    """
    if not store.sidecar_exists():
        return None
    try:
        return store.read_intent()
    except UNREADABLE_DOCUMENT as exc:
        log("system", "warn", f"REE metadata is present but unreadable ({exc}); proceeding without an intent")
        return None


def collect_step_inputs(
    layout: ReeLayout,
    store: ReeDirectory,
    intent: ReeIntent | None,
    script_path: str,
    verify_script_path: str = "",
    *,
    log: LogSink,
) -> StepInputs:
    """Digest the step's inputs as they are at run start.

    The digests mirror the *materialization inputs* a re-runner will have —
    snapshot digest from the lifecycle state, script content, the declared runtime
    artifact's state — never a digest of the live workspace tree.
    """
    snapshot_digest: Digest | None = None
    if store.sidecar_exists():
        try:
            snapshot_digest = store.read_state().source_snapshot_digest
        except UNREADABLE_DOCUMENT as exc:
            # A receipt without a snapshot digest asserts "this REE has no
            # captured source". When the truth is "the lifecycle state could not be
            # read", this line is the only place that difference is recoverable.
            log("system", "warn", f"could not read lifecycle state for this receipt's snapshot digest: {exc}")
    runtime_path = WorkspacePath(intent.runtime) if intent and intent.runtime else None
    return StepInputs(
        snapshot_digest=snapshot_digest,
        script_digest=digest_file_if_exists(layout.workspace / script_path),
        verify_script_digest=(
            digest_file_if_exists(layout.workspace / verify_script_path) if verify_script_path else None
        ),
        runtime_path=runtime_path,
        declared_runtime_digest=(digest_file_if_exists(layout.workspace / runtime_path) if runtime_path else None),
        workspace_drift=check_workspace_drift(
            layout,
            excluded_paths=declared_output_paths(intent) if intent else set(),
        ),
    )


def record_step_inputs(inputs: StepInputs) -> None:
    """Surface the input slice on the command span as soon as it is known."""
    ReceiptInputAttrs(
        snapshot_digest=inputs.snapshot_digest,
        script_digest=inputs.script_digest,
        verify_script_digest=inputs.verify_script_digest,
        runtime_path=inputs.runtime_path,
        declared_runtime_digest=inputs.declared_runtime_digest,
        drift_status=inputs.workspace_drift.status,
        drift_changed_path_count=inputs.workspace_drift.changed_path_count,
    ).apply_current()


def dump_receipt_whole[ReceiptT: RunReceipt](receipt: ReceiptT | None) -> dict[str, Any] | None:
    """Serialize a receipt carried on an outputs envelope, fields and all.

    Attach with ``@field_serializer`` to any ``receipt`` field on an outputs
    model. Envelopes are dumped with ``exclude_none=True``, and that recursion
    must not reach inside the receipt, where a None field is itself the
    evidence: ``produced_runtime_digest: null`` says the build produced nothing
    at the declared path.
    """
    return receipt.model_dump(mode="json") if receipt is not None else None


class RunnableStepOutputs(RunnableRunOutputs):
    """A runnable run's outputs plus the handler-level facts."""

    runtime_path: str = ""
    receipt: ActivationTestReceipt | RunExperimentReceipt | None = None

    _dump_receipt = field_serializer("receipt")(dump_receipt_whole)


class VersionConflictOutputs(BaseModel):
    """Outputs reported when an optimistic-concurrency check loses.

    One shape for both subjects an author can hold a stale version of: a
    workspace file (identified by ``path``, versioned by its content etag) and
    the intent itself (versioned by the sidecar's ``updated_at``). The check is
    the same check, and a client handling one conflict handles both.
    """

    model_config = ConfigDict(extra="forbid")

    error_code: Literal["version_conflict"] = "version_conflict"
    path: str | None = None
    expected_version: str
    actual_version: str | None

    def as_outputs(self) -> dict[str, Any]:
        """The conflict as an outputs blob, without the field that does not apply."""
        return self.model_dump(exclude={"path"} if self.path is None else set())


def result_from_run_outcome(
    status: ActionStatus,
    *,
    exit_code: int | None,
    outputs: dict[str, Any],
    operation: str,
) -> ActionResult:
    """Terminal ActionResult for a script-backed handler.

    A ``failed`` outcome carries an ``execution`` :class:`Failure` and the real
    underlying exit code (never a misleading 0), so a client learns *that* and
    *why* the author's script failed from the result itself, not the log tail.
    """
    if status == "failed":
        return ActionResult.failed(
            "execution",
            f"{operation} failed",
            exit_code=exit_code or 1,
            outputs=outputs,
        )
    return ActionResult(status=status, exit_code=0, outputs=outputs)


def outcome_log_level(status: ActionStatus) -> Literal["info", "warn", "error"]:
    """The level a step's closing line is logged at, keyed to how it ended."""
    if status == "succeeded":
        return "info"
    return "warn" if status == "canceled" else "error"


def log_step_outcome(
    operation: str,
    status: ActionStatus,
    timing: OperationTiming,
    *,
    log: LogSink,
    detail: str = "",
) -> None:
    """Say how a step ended and how long it took, in the one shape every step uses.

    Which operation, which of the three ways it can end, and the duration in
    both a human spelling and the machine one a log scraper keys on. Centralised
    so those two renderings of one duration cannot drift apart.

    ``detail`` appends a step-specific parenthetical (an exit code, say) after
    the status; the rest of the line stays fixed.
    """
    log(
        "system",
        outcome_log_level(status),
        f"{operation} {status}{detail} in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )


def settle_step[ReceiptT: RunReceipt](
    layout: ReeLayout,
    build: Callable[[ReceiptEnvelopeFields], ReceiptT],
    *,
    operation: str,
    run_id: str,
    timer: OperationTimer,
    status: ActionStatus,
    log: LogSink,
    detail: str = "",
) -> ReceiptT:
    """Close a step: stop its clock, receipt it against that clock, and say so.

    The author-side counterpart of the reviewer's ``settle`` exit
    (:mod:`repo2ree_core.operations.steps.review`), for a lifecycle whose record
    is a receipt rather than a persisted attempt. The order is load-bearing: one
    :meth:`OperationTimer.finish` reading feeds both the receipt's envelope and
    the closing log line, so a receipt can never claim a duration the log
    contradicts.

    ``build`` receives the envelope and returns the step's own receipt, so this
    knows nothing about which shapes exist — the same reason
    :attr:`RunnableStep.build_receipt` is a builder rather than a class::

        receipt = settle_step(
            layout,
            lambda envelope: GenerateSbomReceipt(**envelope, runtime_path=path),
            operation="generate_sbom", run_id=run_id, timer=timer,
            status="succeeded", log=log,
        )
    """
    timing = timer.finish()
    receipt = build(receipt_envelope(run_id, timing, status))
    record_receipt(layout, receipt, log=log)
    log_step_outcome(operation, status, timing, log=log, detail=detail)
    return receipt


def _capture_experiment_outputs(
    layout: ReeLayout,
    name: str,
    output_paths: list[str],
    log: LogSink,
) -> Digest | None:
    """Copy an experiment's declared outputs into its produced-results store.

    Always runs after a successful experiment run (independent of sealing): the
    store (``results/<name>/``) is the author-side baseline a reviewer later
    diffs against, and the returned digest binds that baseline into the receipt.
    Returns ``None`` when the experiment declares no outputs. Copies each
    declared path preserving its relative structure so the store mirrors the
    workspace layout; the digest is computed over the live workspace (the source
    of truth), not the copied bytes.
    """
    if not output_paths:
        return None
    store = layout.results_dir(name)
    if store.exists():
        shutil.rmtree(store, ignore_errors=True)
    for rel in output_paths:
        source = resolve_workspace_path(layout, rel)
        if source.is_dir():
            shutil.copytree(source, store / rel, dirs_exist_ok=True)
        elif source.is_file():
            dest = store / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        else:
            log("system", "warn", f"declared output not found, skipping capture: {rel}")
    return digest_output_paths(layout.workspace, output_paths)


RunnableSelector = Callable[[ReeIntent, "LogSink"], tuple[Runnable, str] | None]


@dataclass(frozen=True)
class StepRecord:
    """Everything the shared runner learned about one runnable run.

    The complete input to a step's receipt, assembled by the runner and handed
    to :attr:`RunnableStep.build_receipt` as one typed value: a receipt shape
    needing a fact none of the others do adds a field here, not a parameter to
    every builder.
    """

    run_id: str
    timing: OperationTiming
    status: ActionStatus
    inputs: StepInputs
    runnable: Runnable
    label: str
    run_exit_code: int | None
    verify_exit_code: int | None
    #: Digest of the declared outputs captured after a successful run, or None
    #: when the step captures none (see ``captures_declared_outputs``).
    produced_output_digest: Digest | None


def step_receipt_fields(record: StepRecord) -> RunnableStepFields:
    """The receipt fields every runnable step records, whatever shape it takes.

    Spread into the receipt a builder constructs (``**step_receipt_fields(...)``,
    the same idiom as :func:`receipt_envelope`, which it includes). These are the
    fields that make a receipt auditable — the input slice collected before the
    run, bound to what the run did — so no builder spells them itself.

    Typed rather than a plain mapping so the spread stays checked: a receipt
    field renamed on one side only is a type error here, not a validation error
    thrown away at the end of the run it was recording.
    """
    return RunnableStepFields(
        **receipt_envelope(record.run_id, record.timing, record.status),
        workspace_drift=record.inputs.workspace_drift,
        snapshot_digest=record.inputs.snapshot_digest,
        run_script_path=ScriptPath(record.runnable.run_script),
        run_script_digest=record.inputs.script_digest,
        run_exit_code=record.run_exit_code,
        verify_script_path=ScriptPath(record.runnable.verify_script) if record.runnable.verify_script else None,
        verify_script_digest=record.inputs.verify_script_digest,
        verify_exit_code=record.verify_exit_code,
        runtime_path=record.inputs.runtime_path,
        declared_runtime_digest=record.inputs.declared_runtime_digest,
    )


ReceiptBuilder = Callable[[StepRecord], ActivationTestReceipt | RunExperimentReceipt]


@dataclass(frozen=True)
class RunnableStep:
    """Everything that distinguishes one runnable step from another.

    Activation and experiments execute identically — that is what
    :class:`~repo2ree_core.domain.experiment.Runnable` means — and differ only
    in what they *record*: what shape their evidence takes, and whether a
    successful run has declared outputs to capture as a reviewer's baseline.

    ``build_receipt`` is a builder rather than a receipt class so the runner
    never has to interrogate a receipt to finish filling it in.
    """

    operation: str
    select: RunnableSelector
    build_receipt: ReceiptBuilder
    captures_declared_outputs: bool


def run_runnable_handler(
    step: RunnableStep,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    """Run the step's selected :class:`Runnable` and record its receipt.

    ``step.select`` logs and returns ``None`` when the runnable can't be
    resolved.
    """
    opened = open_ree_store(log)
    if isinstance(opened, ActionResult):
        return opened
    layout, store = opened

    try:
        ree = store.read_intent()
    except UNREADABLE_DOCUMENT as exc:
        log("system", "error", f"Invalid REE intent: {exc}")
        return ActionResult.failed("internal", f"Invalid REE intent: {exc}")

    selected = step.select(ree, log)
    if selected is None:
        # ``select`` has already logged why the runnable could not be resolved.
        return ActionResult.failed("precondition", f"{step.operation} target could not be resolved")
    runnable, label = selected

    timer = OperationTimer.start()
    inputs = collect_step_inputs(layout, store, ree, runnable.run_script, runnable.verify_script, log=log)
    record_step_inputs(inputs)

    outcome = run_runnable(
        workspace=layout.workspace.resolve(),
        runnable=runnable,
        label=label,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    outputs = RunnableStepOutputs(
        **outcome.run_outputs.model_dump(),
        runtime_path=ree.runtime or "",
    )

    status: ActionStatus = outcome.status

    # Capture declared outputs after a successful run, for the steps that have
    # a baseline to leave behind (activation produces no sealed result). Always
    # copies to the produced-results store — whether the store is packaged is an
    # all-or-nothing seal-time choice (`results_included`) handled at bundle
    # time, not per-experiment state.
    produced_output_digest: Digest | None = None
    if step.captures_declared_outputs and status == "succeeded" and runnable.output_paths:
        produced_output_digest = _capture_experiment_outputs(layout, label, runnable.output_paths, log)

    timing = timer.finish()
    receipt = step.build_receipt(
        StepRecord(
            run_id=run_id,
            timing=timing,
            status=status,
            inputs=inputs,
            runnable=runnable,
            label=label,
            run_exit_code=outcome.run_outputs.exit_code,
            verify_exit_code=outcome.run_outputs.verify_exit_code,
            produced_output_digest=produced_output_digest,
        )
    )
    record_receipt(layout, receipt, log=log)
    outputs.receipt = receipt
    log_step_outcome(step.operation, status, timing, log=log)

    return result_from_run_outcome(
        status,
        exit_code=outcome.run_outputs.verify_exit_code or outcome.run_outputs.exit_code,
        outputs=outputs.model_dump(exclude_none=True),
        operation=step.operation,
    )


def workspace_content_etag(store: ReeDirectory, path: str) -> str | None:
    """Current canonical etag of a workspace file, or None if it is absent.

    The API computes the etag it hands back after a write with the same
    ``digest_bytes``; the two are compared across a process boundary, so they
    must not be spelled independently.
    """
    if not store.workspace.is_file(path):
        return None
    return digest_bytes(store.workspace.read_bytes(path))


def check_expected_etag(store: ReeDirectory, path: str, expected: str, *, log: LogSink) -> ActionResult | None:
    """Verify an optimistic-concurrency etag; return the conflict result on mismatch.

    Runs inside the per-REE dispatch serialization, so a passed check cannot be
    invalidated before the mutation that follows it. Empty ``expected`` skips
    the check.
    """
    if not expected:
        return None
    actual = workspace_content_etag(store, path)
    if expected == actual:
        return None
    log("system", "error", f"etag mismatch for {path}: expected {expected}, actual {actual}")
    return ActionResult.failed(
        "conflict",
        f"etag mismatch for {path}: expected {expected}, actual {actual}",
        retryable=True,
        outputs=VersionConflictOutputs(
            path=path,
            expected_version=expected,
            actual_version=actual,
        ).as_outputs(),
    )


def patch_ree_intent(store: ReeDirectory, patch: dict[str, Any]) -> None:
    if not store.sidecar_exists():
        raise FileNotFoundError("metadata not found")
    transition = patch_intent(load_ree(store.layout, store), patch)
    store.write_intent(transition.authored.intent)

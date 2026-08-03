"""Handler for the read-only script-inference command.

Inference scans the immutable ``upstream`` tree (never the materialized
workspace, so it can never discover its own generated output as evidence),
runs the versioned decision DAGs, and returns the full ``InferenceReport`` in
the result outputs. It is synchronous, deterministic, persists nothing, and
writes no files — turning a candidate into a script stays on the existing
``write_file`` path.
"""

from __future__ import annotations

from repo2ree_core.authoring.script_inference import ScriptTargetSelector, infer_scripts
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.handlers.author._script_inference_inputs import build_runtime_inputs
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import GenerateScriptCandidatesArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_generate_script_candidates(
    args: GenerateScriptCandidatesArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if not args.targets:
        return ActionResult.failed("validation", "no inference targets requested")

    layout = ReeLayout.in_workbench()
    upstream = layout.upstream
    if not upstream.is_dir():
        log("system", "error", "no acquired source to infer from")
        return ActionResult.failed("precondition", "no acquired source (upstream tree is absent)")

    store = ReeDirectory(layout)
    definition = store.read_ree().subject.definition if store.record_exists() else None
    ree_id, snapshot_digest = _identity(store)
    runtime_inputs = build_runtime_inputs(layout, definition)

    selectors = [
        ScriptTargetSelector(kind=target.kind, experiment_name=target.experiment_name) for target in args.targets
    ]

    try:
        report = infer_scripts(
            upstream,
            selectors,
            definition=definition,
            runtime_inputs=runtime_inputs,
            ree_id=ree_id,
            source_snapshot_digest=snapshot_digest,
        )
    except ValueError as exc:
        # A malformed selector (experiment name present/absent for the wrong
        # kind) is a bad request, not an internal fault.
        log("system", "error", f"invalid inference target: {exc}")
        return ActionResult.failed("validation", f"invalid inference target: {exc}")
    except Exception as exc:
        log("system", "error", f"generate_script_candidates failed: {exc}")
        return failed_from_exception(exc, f"generate_script_candidates failed: {exc}")

    if is_canceled():
        log("system", "warn", "generate_script_candidates canceled")
        return ActionResult(status="canceled")

    inferred = sum(1 for result in report.results if result.status != "not_inferred")
    log("system", "info", f"inference produced results for {len(report.results)} target(s); {inferred} with candidates")
    return ActionResult(status="succeeded", exit_code=0, outputs=report.model_dump())


def _identity(store: ReeDirectory) -> tuple[str, str | None]:
    if not store.record_exists():
        return "", None
    source = store.read_ree().subject.receipts.source
    return "", str(source.snapshot_digest) if source else None

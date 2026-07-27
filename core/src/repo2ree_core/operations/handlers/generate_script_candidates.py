"""Handler for the read-only script-inference command.

Inference scans the immutable ``upstream`` tree (never the materialized
workspace, so it can never discover its own generated output as evidence),
runs the versioned decision DAGs, and returns the full ``InferenceReport`` in
the result outputs. It is synchronous, deterministic, persists nothing, and
writes no files — turning a candidate into a script stays on the existing
``write_file`` path.
"""

from __future__ import annotations

from contextlib import suppress

from repo2ree_core.authoring.script_inference import ScriptTargetSelector, infer_scripts
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.handlers._script_inference_inputs import build_runtime_inputs
from repo2ree_core.operations.handlers.step_runner import read_intent_or_none
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore
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

    store = ReeStore(layout)
    intent = read_intent_or_none(store, log=log)
    ree_id, snapshot_digest = _identity(store)
    runtime_inputs = build_runtime_inputs(layout, intent)

    selectors = [
        ScriptTargetSelector(kind=target.kind, experiment_name=target.experiment_name) for target in args.targets
    ]

    try:
        report = infer_scripts(
            upstream,
            selectors,
            intent=intent,
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
        return ActionResult.failed("internal", f"generate_script_candidates failed: {exc}")

    if is_canceled():
        log("system", "warn", "generate_script_candidates canceled")
        return ActionResult(status="canceled")

    inferred = sum(1 for result in report.results if result.status != "not_inferred")
    log("system", "info", f"inference produced results for {len(report.results)} target(s); {inferred} with candidates")
    return ActionResult(status="succeeded", exit_code=0, outputs=report.model_dump())


def _identity(store: ReeStore) -> tuple[str, str | None]:
    ree_id = ""
    snapshot_digest: str | None = None
    with suppress(Exception):
        if store.metadata_exists():
            metadata = store.read_metadata()
            ree_id = metadata.ree_id
            snapshot_digest = metadata.ree_session.source_snapshot_digest
    return ree_id, snapshot_digest

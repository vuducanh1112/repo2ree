from __future__ import annotations

from repo2ree_core.author_recipes.inference import infer_scripts
from repo2ree_core.author_recipes.inference.machine import EngineProbe, MachineInputs, SlurmProbeSource
from repo2ree_core.execution.engine_probe import RunnerEngineProbe
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.execution.slurm_probe import RunnerSlurmProbe
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.handlers.author._script_inference_inputs import build_experiment_environment_inputs
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import ScriptTargetSelectorArg, SuggestScriptsArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult


def engine_probe(layout: ReeLayout) -> EngineProbe:
    return RunnerEngineProbe(layout.workspace)


def slurm_probe(layout: ReeLayout) -> SlurmProbeSource:
    return RunnerSlurmProbe(layout.workspace)


def handle_suggest_scripts(
    args: SuggestScriptsArgs,
    *,
    layout: ReeLayout,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if not args.targets:
        return ActionResult.failed("validation", "no inference targets requested")

    upstream = layout.upstream
    if not upstream.is_dir():
        log("system", "error", "no acquired source to infer from")
        return ActionResult.failed("precondition", "no acquired source (upstream tree is absent)")

    store = ReeDirectory(layout)
    ree = store.read_ree() if store.manifest_exists() else None
    definition = ree.subject.definition if ree else None
    source_receipt = ree.subject.receipts.acquire_source if ree else None
    snapshot_digest = str(source_receipt.snapshot_digest) if source_receipt else None
    experiment_environment_inputs = build_experiment_environment_inputs(layout, definition)

    selectors = [
        ScriptTargetSelectorArg(kind=target.kind, experiment_name=target.experiment_name) for target in args.targets
    ]

    try:
        report = infer_scripts(
            upstream,
            selectors,
            definition=definition,
            experiment_environment_inputs=experiment_environment_inputs,
            machine=MachineInputs(engines=engine_probe(layout), slurm=slurm_probe(layout)),
            source_snapshot_digest=snapshot_digest,
        )
    except ValueError as exc:
        log("system", "error", f"invalid inference target: {exc}")
        return ActionResult.failed("validation", f"invalid inference target: {exc}")
    except Exception as exc:
        log("system", "error", f"suggest_scripts failed: {exc}")
        return failed_from_exception(exc, f"suggest_scripts failed: {exc}")

    if is_canceled():
        log("system", "warn", "suggest_scripts canceled")
        return ActionResult(status="canceled")

    inferred = sum(1 for result in report.results if result.status != "not_inferred")
    log("system", "info", f"inference produced results for {len(report.results)} target(s); {inferred} with candidates")
    return ActionResult(status="succeeded", exit_code=0, outputs=report.model_dump())

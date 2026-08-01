from __future__ import annotations

from repo2ree_core.domain.experiment import Runnable
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.receipt import RunExperimentReceipt
from repo2ree_core.execution.experiment.resolve import RunnableResolutionError, resolve_experiment_runnable
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.steps.author import (
    RunnableStep,
    StepRecord,
    run_runnable_handler,
    step_receipt_fields,
)
from repo2ree_protocol.command import RunExperimentArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_run_experiment(
    args: RunExperimentArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    def select(ree: ReeIntent, log: LogSink) -> tuple[Runnable, str] | None:
        try:
            experiment = resolve_experiment_runnable(ree, args.experiment_name)
        except RunnableResolutionError as exc:
            log("system", "error", str(exc))
            return None
        if not ree.runtime:
            log(
                "system",
                "warn",
                "No runtime artifact declared — the run is native and its receipt carries no runtime binding",
            )
        return experiment, experiment.name

    def build_receipt(record: StepRecord) -> RunExperimentReceipt:
        # The two facts only an experiment has: which of the REE's experiments
        # this receipt is about, and the digest of the baseline it left behind.
        return RunExperimentReceipt(
            **step_receipt_fields(record),
            experiment_name=record.label,
            produced_output_digest=record.produced_output_digest,
        )

    return run_runnable_handler(
        RunnableStep(
            operation="run_experiment",
            select=select,
            build_receipt=build_receipt,
            # An experiment's declared outputs are the author-side baseline a
            # reviewer later diffs against, so a successful run captures them.
            captures_declared_outputs=True,
        ),
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )

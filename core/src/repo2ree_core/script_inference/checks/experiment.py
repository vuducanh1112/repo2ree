"""The experiment-declaration gate for experiment-run inference.

Experiment inference only proceeds for an experiment the author has actually
declared on the REE. The requested name (carried on the decision context because
it lives on the target, not the scan) must match exactly one
``ReeIntent.experiments`` entry; its reserved run/verify paths and declared
output paths become an ``ExperimentBinding`` the downstream renderer consumes.
An undeclared experiment blocks straight to ``not_inferred``.
"""

from __future__ import annotations

from repo2ree_core.script_inference.models import (
    BindingKind,
    CheckResult,
    DecisionContext,
    ExperimentBinding,
    ExperimentGateObservation,
)
from repo2ree_core.script_inference.warnings import make_warning


class RequestedExperimentCheck:
    code = "requested_experiment"
    label = "Is the requested experiment declared on the REE?"
    branches = frozenset({"absent", "found"})
    requires: frozenset[BindingKind] = frozenset()
    produces: dict[str, frozenset[BindingKind]] = {
        "absent": frozenset(),
        "found": frozenset({"experiment"}),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        name = context.requested_experiment
        experiment = context.runtime.experiment(name) if name else None
        if experiment is None:
            return CheckResult(
                branch="absent",
                observed=ExperimentGateObservation(result="absent", requested=name, declared=False),
                warnings=[make_warning("experiment_not_declared")],
            )
        binding = ExperimentBinding(
            name=experiment.name,
            run_script_path=experiment.run_script,
            verify_script_path=experiment.verify_script or None,
            output_paths=list(experiment.output_paths),
        )
        return CheckResult(
            branch="found",
            observed=ExperimentGateObservation(result="found", requested=name, declared=True),
            bindings=(binding,),
        )

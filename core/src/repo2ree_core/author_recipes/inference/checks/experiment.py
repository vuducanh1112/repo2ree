"""The experiment-declaration gate for experiment-run inference.

Experiment inference proceeds for a named experiment, declared or not: declaring
one needs its run script, so inference has to come first. The requested name
(carried on the decision context because it lives on the target, not the scan)
matches a ``ReeDefinition.experiments`` entry or the reserved slug convention; its
run/verify paths and declared output paths become an ``ExperimentBinding`` the
downstream renderer consumes. A request with no name blocks to ``not_inferred``.
"""

from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.inference.models import BindingKind, CheckResult, DecisionContext
from repo2ree_core.author_recipes.inference.warnings import make_warning
from repo2ree_protocol.inference import ExperimentBinding, ExperimentGateObservation
from repo2ree_ree.reserved_paths import experiment_run_script_path


class RequestedExperimentCheck:
    code = "requested_experiment"
    label = "Does the request name an experiment?"
    branches = frozenset({"absent", "found"})
    requires: frozenset[BindingKind] = frozenset()
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "absent": frozenset(),
        "found": frozenset({"experiment"}),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        name = context.requested_experiment
        if not name:
            return CheckResult(
                branch="absent",
                observed=ExperimentGateObservation(result="absent", requested=name, declared=False),
                warnings=[make_warning("experiment_not_named")],
            )
        experiment = context.runtime.experiment(name)
        if experiment is None:
            return CheckResult(
                branch="found",
                observed=ExperimentGateObservation(result="found", requested=name, declared=False),
                bindings=(
                    ExperimentBinding(name=name, run_script_path=experiment_run_script_path(name), output_paths=[]),
                ),
                warnings=[make_warning("experiment_not_declared")],
            )
        binding = ExperimentBinding(
            name=experiment.name,
            run_script_path=str(experiment.run_script_path),
            verify_script_path=str(experiment.verify_script_path) if experiment.verify_script_path else None,
            output_paths=list(experiment.output_paths),
        )
        return CheckResult(
            branch="found",
            observed=ExperimentGateObservation(result="found", requested=name, declared=True),
            bindings=(binding,),
        )

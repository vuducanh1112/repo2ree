from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.inference.models import BindingKind, CheckResult, DecisionContext
from repo2ree_core.author_recipes.inference.warnings import make_warning
from repo2ree_protocol.inference import SlurmObservation


class SlurmCheck:
    code = "slurm"
    label = "Can this REE's scripts be launched as Slurm job steps where they run?"
    branches = frozenset({"usable", "unavailable", "unknown"})
    requires: frozenset[BindingKind] = frozenset()
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "usable": frozenset(),
        "unavailable": frozenset(),
        "unknown": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        probe = context.machine.slurm.probe()
        observed = SlurmObservation(probe=probe)
        if probe.status != "probed":
            warning = make_warning("slurm_not_probed")
            warning.details = {"probe": probe.status, "detail": probe.detail}
            return CheckResult(branch="unknown", observed=observed, warnings=[warning])
        if probe.state == "usable":
            return CheckResult(branch="usable", observed=observed)
        warning = make_warning("slurm_unavailable")
        warning.details = {"state": probe.state, "detail": probe.detail}
        return CheckResult(branch="unavailable", observed=observed, warnings=[warning])

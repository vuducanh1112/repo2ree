"""Container-engine checks: whether a script driving an engine would run where the REE's scripts run.

A container file can be built by Docker or by Podman, and an image archive loaded by either, so each engine
is its own strategy, and these decide whether its script is runnable. They read the machine through the
context's probe: a probed, usable engine is runnable; a probed engine that is absent or unreachable is not;
and when nothing could be probed, nothing is known, which proposes the engine's script for confirmation
rather than ruling it out.
"""

from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.inference.models import BindingKind, CheckResult, DecisionContext
from repo2ree_core.author_recipes.inference.warnings import make_warning
from repo2ree_protocol.inference import (
    ContainerEngine,
    ContainerEnginesObservation,
    DockerExperimentEnvironmentContract,
    ExperimentEnvironmentContractBinding,
    ExperimentEnvironmentContractObservation,
)


class ContainerEngineCheck:
    """Is ``engine`` usable where this REE's scripts run?"""

    branches = frozenset({"usable", "unavailable", "unknown"})
    requires: frozenset[BindingKind] = frozenset()
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "usable": frozenset(),
        "unavailable": frozenset(),
        "unknown": frozenset(),
    }

    def __init__(self, engine: ContainerEngine) -> None:
        self.engine: ContainerEngine = engine
        self.code = f"{engine}_engine"
        self.label = f"Is {engine} usable where this REE's scripts run?"

    def evaluate(self, context: DecisionContext) -> CheckResult:
        probe = context.machine.engines.probe()
        observed = ContainerEnginesObservation(engine=self.engine, probe=probe)
        if probe.status != "probed":
            warning = make_warning("container_engines_not_probed")
            warning.details = {"probe": probe.status, "detail": probe.detail}
            return CheckResult(branch="unknown", observed=observed, warnings=[warning])
        seen = next((engine for engine in probe.engines if engine.engine == self.engine), None)
        if seen is not None and seen.state == "usable":
            return CheckResult(branch="usable", observed=observed)
        warning = make_warning(f"{self.engine}_unavailable")
        warning.details = {"state": seen.state if seen else "absent", "detail": seen.detail if seen else None}
        return CheckResult(branch="unavailable", observed=observed, warnings=[warning])


class ContractEngineCheck:
    """Which engine built the image archive, when a generated build says so."""

    code = "experiment_environment_engine"
    label = "Which engine's store holds the experiment environment image?"
    branches = frozenset({"docker", "podman", "unknown"})
    requires: frozenset[BindingKind] = frozenset({"experiment_environment_contract"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "docker": frozenset(),
        "podman": frozenset(),
        "unknown": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        binding = context.binding("experiment_environment_contract")
        if not isinstance(binding, ExperimentEnvironmentContractBinding) or not isinstance(
            binding.contract, DockerExperimentEnvironmentContract
        ):
            raise ValueError("experiment_environment_engine check reached without an image archive contract")
        engine = binding.contract.engine
        branch = engine or "unknown"
        return CheckResult(
            branch=branch,
            observed=ExperimentEnvironmentContractObservation(
                result=branch,
                experiment_environment_kind=binding.contract.kind,
                provenance=binding.provenance,
                detail=f"built by {engine}" if engine else "the archive does not say which engine built it",
            ),
        )

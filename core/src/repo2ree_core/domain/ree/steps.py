"""Where an REE stands on the steps of authoring it, and what to do next.

A step is ``complete`` when the REE's own records say so: a receipt the audit
finds ``current``, or a declaration the definition holds. Nothing an author ran
but the REE did not record counts, so every reader — ``ree status``, the API, the
GUI — gets the same answer from the same REE.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from repo2ree_protocol.audit import ReeAudit, StepAudit
from repo2ree_protocol.catalog import ReeStep, ReeStepKey, ReeSteps, ReeStepState, ReeStepStatus
from repo2ree_protocol.command import (
    AcquireSourceCommand,
    ActivateExperimentEnvironmentCommand,
    BuildExperimentEnvironmentCommand,
    CheckWorkingEnvironmentCommand,
    CrossCheckSbomCommand,
    EvaluateReproducibilityCommand,
    GenerateSbomCommand,
    ObserveHardwareCommand,
    PatchReeDefinitionCommand,
    RunExperimentCommand,
    SealReeCommand,
    SuggestScriptsCommand,
    WriteScriptCommand,
)
from repo2ree_protocol.verbs import VERBS
from repo2ree_ree.model import Ree


def _commands(*commands: type[BaseModel]) -> list[str]:
    return [" ".join(VERBS[command]) for command in commands]


REE_STEPS: tuple[ReeStep, ...] = (
    ReeStep(key="acquire_source", order=1, label="Source Acquisition", commands=_commands(AcquireSourceCommand)),
    ReeStep(key="metadata", order=2, label="Provide Metadata", commands=_commands(PatchReeDefinitionCommand)),
    ReeStep(
        key="observe_hardware",
        order=3,
        label="Hardware BOM",
        commands=_commands(ObserveHardwareCommand, PatchReeDefinitionCommand),
    ),
    ReeStep(
        key="check_working_environment",
        order=4,
        label="Check Working Environment",
        commands=_commands(WriteScriptCommand, PatchReeDefinitionCommand, CheckWorkingEnvironmentCommand),
    ),
    ReeStep(
        key="evaluate_reproducibility",
        order=5,
        label="Reproducibility Readiness",
        requires=["acquire_source"],
        commands=_commands(EvaluateReproducibilityCommand),
    ),
    ReeStep(
        key="build_experiment_environment",
        order=6,
        label="Build Experiment Environment",
        requires=["acquire_source"],
        commands=_commands(BuildExperimentEnvironmentCommand, SuggestScriptsCommand, WriteScriptCommand),
    ),
    ReeStep(
        key="generate_sbom",
        order=7,
        label="Generate SBOM",
        requires=["build_experiment_environment"],
        commands=_commands(GenerateSbomCommand),
    ),
    ReeStep(
        key="cross_check_sbom",
        order=8,
        label="Cross-check SBOM",
        requires=["generate_sbom", "evaluate_reproducibility"],
        commands=_commands(CrossCheckSbomCommand),
    ),
    ReeStep(
        key="activate_experiment_environment",
        order=9,
        label="Test Activation",
        requires=["build_experiment_environment"],
        commands=_commands(ActivateExperimentEnvironmentCommand),
    ),
    ReeStep(
        key="experiments",
        order=10,
        label="Experiments",
        requires=["activate_experiment_environment"],
        commands=_commands(RunExperimentCommand, PatchReeDefinitionCommand, SuggestScriptsCommand, WriteScriptCommand),
    ),
    ReeStep(key="seal_ree", order=11, label="Seal", commands=_commands(SealReeCommand)),
)


def _current(step: Callable[[ReeAudit], StepAudit]) -> Callable[[Ree, ReeAudit], bool]:
    return lambda _ree, audit: step(audit).evidence == "current"


def _metadata_given(ree: Ree, _audit: ReeAudit) -> bool:
    definition = ree.subject.definition
    return all(value.strip() for value in (definition.name, definition.catalog.version, definition.catalog.description))


def _hardware_described(ree: Ree, audit: ReeAudit) -> bool:
    """Observed on a machine, or required by the definition: either describes the hardware."""
    if audit.observe_hardware.evidence == "current":
        return True
    hardware = ree.subject.definition.hbom
    return hardware is not None and any(
        (hardware.cpus, hardware.gpus, hardware.memory, hardware.storage, hardware.network)
    )


def _experiments_ran(ree: Ree, audit: ReeAudit) -> bool:
    """Some experiment is declared, and each one's run is current."""
    return bool(ree.subject.definition.experiments) and all(
        experiment.run.evidence == "current" for experiment in audit.experiments
    )


_COMPLETE: dict[ReeStepKey, Callable[[Ree, ReeAudit], bool]] = {
    "acquire_source": _current(lambda audit: audit.acquire_source),
    "metadata": _metadata_given,
    "observe_hardware": _hardware_described,
    "check_working_environment": _current(lambda audit: audit.check_working_environment),
    "evaluate_reproducibility": _current(lambda audit: audit.evaluate_reproducibility),
    "build_experiment_environment": _current(lambda audit: audit.build_experiment_environment),
    "generate_sbom": _current(lambda audit: audit.generate_sbom),
    "cross_check_sbom": _current(lambda audit: audit.cross_check_sbom),
    "activate_experiment_environment": _current(lambda audit: audit.activate_experiment_environment),
    "experiments": _experiments_ran,
    "seal_ree": lambda ree, _audit: ree.seal is not None,
}


def ree_steps(ree: Ree, audit: ReeAudit) -> ReeSteps:
    """Each step's status for ``ree``, whose audit is ``audit``, and the lowest-order ready step as the next: none
    once sealed, since a sealed REE takes no step."""
    complete = {step.key for step in REE_STEPS if _COMPLETE[step.key](ree, audit)}

    def status(step: ReeStep) -> ReeStepStatus:
        if step.key in complete:
            return "complete"
        return "ready" if all(required in complete for required in step.requires) else "blocked"

    states = [ReeStepState(**step.model_dump(), status=status(step)) for step in REE_STEPS]
    ready = [state for state in states if state.status == "ready" and ree.seal is None]
    return ReeSteps(steps=states, next=min(ready, key=lambda state: state.order).key if ready else None)

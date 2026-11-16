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
    ActivationTestCommand,
    BuildExperimentEnvironmentCommand,
    CheckWorkingEnvironmentCommand,
    CrossCheckSbomCommand,
    EvaluateDependencyScoreCommand,
    GenerateHbomCommand,
    GenerateSbomCommand,
    GenerateScriptCandidatesCommand,
    PatchReeDefinitionCommand,
    RunExperimentCommand,
    SealReeCommand,
    WriteFileCommand,
)
from repo2ree_protocol.verbs import VERBS
from repo2ree_ree.model import Ree


def _commands(*commands: type[BaseModel]) -> list[str]:
    return [" ".join(VERBS[command]) for command in commands]


REE_STEPS: tuple[ReeStep, ...] = (
    ReeStep(key="source", order=1, label="Source Acquisition", commands=_commands(AcquireSourceCommand)),
    ReeStep(key="metadata", order=2, label="Provide Metadata", commands=_commands(PatchReeDefinitionCommand)),
    ReeStep(
        key="hbom",
        order=3,
        label="Hardware BOM",
        commands=_commands(GenerateHbomCommand, PatchReeDefinitionCommand),
    ),
    ReeStep(
        key="check_working_environment",
        order=4,
        label="Check Working Environment",
        commands=_commands(WriteFileCommand, PatchReeDefinitionCommand, CheckWorkingEnvironmentCommand),
    ),
    ReeStep(
        key="evaluate",
        order=5,
        label="Reproducibility Readiness",
        requires=["source"],
        commands=_commands(EvaluateDependencyScoreCommand),
    ),
    ReeStep(
        key="build_experiment_environment",
        order=6,
        label="Build Experiment Environment",
        requires=["source"],
        commands=_commands(BuildExperimentEnvironmentCommand, GenerateScriptCandidatesCommand, WriteFileCommand),
    ),
    ReeStep(
        key="sbom",
        order=7,
        label="Generate SBOM",
        requires=["build_experiment_environment"],
        commands=_commands(GenerateSbomCommand),
    ),
    ReeStep(
        key="crosscheck",
        order=8,
        label="Cross-check SBOM",
        requires=["sbom", "evaluate"],
        commands=_commands(CrossCheckSbomCommand),
    ),
    ReeStep(
        key="activation",
        order=9,
        label="Test Activation",
        requires=["build_experiment_environment"],
        commands=_commands(ActivationTestCommand),
    ),
    ReeStep(
        key="experiments",
        order=10,
        label="Experiments",
        requires=["build_experiment_environment"],
        commands=_commands(
            RunExperimentCommand, PatchReeDefinitionCommand, GenerateScriptCandidatesCommand, WriteFileCommand
        ),
    ),
    ReeStep(key="seal", order=11, label="Seal", commands=_commands(SealReeCommand)),
)


def _current(step: Callable[[ReeAudit], StepAudit]) -> Callable[[Ree, ReeAudit], bool]:
    return lambda _ree, audit: step(audit).evidence == "current"


def _metadata_given(ree: Ree, _audit: ReeAudit) -> bool:
    definition = ree.subject.definition
    return all(value.strip() for value in (definition.name, definition.catalog.version, definition.catalog.description))


def _hardware_described(ree: Ree, _audit: ReeAudit) -> bool:
    hardware = ree.subject.definition.hardware
    return hardware is not None and any(
        (hardware.cpus, hardware.gpus, hardware.memory, hardware.storage, hardware.network)
    )


_COMPLETE: dict[ReeStepKey, Callable[[Ree, ReeAudit], bool]] = {
    "source": _current(lambda audit: audit.source),
    "metadata": _metadata_given,
    "hbom": _hardware_described,
    "check_working_environment": _current(lambda audit: audit.working_environment_check),
    "evaluate": _current(lambda audit: audit.evaluation),
    "build_experiment_environment": _current(lambda audit: audit.experiment_environment),
    "sbom": _current(lambda audit: audit.sbom),
    "crosscheck": _current(lambda audit: audit.sbom_cross_check),
    "activation": _current(lambda audit: audit.activation),
    "experiments": lambda ree, _audit: bool(ree.subject.definition.experiments),
    "seal": lambda ree, _audit: ree.seal is not None,
}


def ree_steps(ree: Ree, audit: ReeAudit) -> ReeSteps:
    """Each step's status for ``ree``, whose audit is ``audit``, and the lowest-order ready step as the next."""
    complete = {step.key for step in REE_STEPS if _COMPLETE[step.key](ree, audit)}

    def status(step: ReeStep) -> ReeStepStatus:
        if step.key in complete:
            return "complete"
        return "ready" if all(required in complete for required in step.requires) else "blocked"

    states = [ReeStepState(**step.model_dump(), status=status(step)) for step in REE_STEPS]
    ready = [state for state in states if state.status == "ready"]
    return ReeSteps(steps=states, next=min(ready, key=lambda state: state.order).key if ready else None)

"""What an author is offered: the steps of authoring an REE, where an REE stands on them, and script templates."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.command import TargetKind

ReeStepKey = Literal[
    "acquire_source",
    "metadata",
    "observe_hardware",
    "check_working_environment",
    "evaluate_reproducibility",
    "build_experiment_environment",
    "generate_sbom",
    "cross_check_sbom",
    "activate_experiment_environment",
    "experiments",
    "seal_ree",
]
# ``complete``: the REE's records show the step done and still true of the REE as it stands.
# ``ready``: every step it needs is complete. ``blocked``: some step it needs is not.
ReeStepStatus = Literal["complete", "ready", "blocked"]


class ReeStep(BaseModel):
    """One authoring step: its place in the order, the steps it needs first, and the ``ree`` commands that do it."""

    model_config = ConfigDict(extra="forbid")

    key: ReeStepKey
    order: int
    label: str
    requires: list[ReeStepKey] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)


class ReeStepState(ReeStep):
    """A step as one REE stands on it."""

    status: ReeStepStatus


class ReeSteps(BaseModel):
    """Where an REE stands on every step, and the one to do next: the first ready one."""

    model_config = ConfigDict(extra="forbid")

    steps: list[ReeStepState] = Field(default_factory=list)
    next: ReeStepKey | None = None


class ScriptTemplateEntry(BaseModel):
    """One named starter-template variant for an REE-owned script.

    Every catalog section lists these; its first entry carries ``is_default`` (for the seeded scripts it is the
    content a fresh REE starts with).
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    description: str
    body: str
    is_default: bool


class ReservedScriptTemplates(BaseModel):
    """The templates of a script an REE has once, and the reserved path it belongs at."""

    model_config = ConfigDict(extra="forbid")

    path: str
    templates: list[ScriptTemplateEntry]


class ExperimentScriptTemplates(BaseModel):
    """The templates of a script every experiment has, and the path it belongs at.

    The pattern carries a ``{slug}`` placeholder: the experiment name with whitespace collapsed to hyphens.
    """

    model_config = ConfigDict(extra="forbid")

    path_pattern: str
    templates: list[ScriptTemplateEntry]


class ScriptTemplateCatalog(BaseModel):
    """Each script kind's templates and where its scripts belong."""

    model_config = ConfigDict(extra="forbid")

    build_experiment_environment: ReservedScriptTemplates
    activate_experiment_environment: ReservedScriptTemplates
    launch: ReservedScriptTemplates
    check_working_environment: ReservedScriptTemplates
    experiment_run: ExperimentScriptTemplates
    experiment_verify: ExperimentScriptTemplates

    def of(self, kind: TargetKind) -> ReservedScriptTemplates | ExperimentScriptTemplates:
        templates: ReservedScriptTemplates | ExperimentScriptTemplates = getattr(self, kind)
        return templates

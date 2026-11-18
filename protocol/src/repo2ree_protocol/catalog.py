"""What an author is offered: the steps of authoring an REE, where an REE stands on them, and script templates."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class BuildExperimentEnvironmentScriptTemplates(BaseModel):
    """The build-script templates and the reserved path they all belong at.

    One entry per standard runtime-packaging strategy; the default entry for an
    environment (``is_default``) is the content a fresh REE's build script there is
    seeded with.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    templates: list[ScriptTemplateEntry]


class ActivateExperimentEnvironmentScriptTemplates(BaseModel):
    """The activate experiment environment templates and the reserved path they all belong at."""

    model_config = ConfigDict(extra="forbid")

    path: str
    templates: list[ScriptTemplateEntry]


class LaunchScriptTemplates(BaseModel):
    """The launch-script templates and the reserved path they belong at.

    Optional: an REE with no launch script runs every script directly. With one, the workbench and ``run.sh`` run
    each script through it, ``sh launch.sh <command>``.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    templates: list[ScriptTemplateEntry]


class CheckWorkingEnvironmentScriptTemplates(BaseModel):
    """The check-script templates and the reserved path they belong at.

    Every REE starts with the first, which checks nothing and passes; the author uncomments what the scripts need.
    The check runs in the working environment, launched as every script is, and must exit 0.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    templates: list[ScriptTemplateEntry]


class ExperimentScriptTemplates(BaseModel):
    """Templates for per-experiment run scripts, plus the path convention they follow.

    The path patterns carry a ``{slug}`` placeholder: the experiment name with
    whitespace collapsed to hyphens. Naming an experiment on the intent settles
    its ``run_script`` to this convention server-side; the patterns are
    published so clients can show the destination before the intent round-trips.
    """

    model_config = ConfigDict(extra="forbid")

    run_script_path_pattern: str
    verify_script_path_pattern: str
    templates: list[ScriptTemplateEntry]


class ScriptTemplateCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_experiment_environment: BuildExperimentEnvironmentScriptTemplates
    activate_experiment_environment: ActivateExperimentEnvironmentScriptTemplates
    launch: LaunchScriptTemplates
    check_working_environment: CheckWorkingEnvironmentScriptTemplates
    experiment: ExperimentScriptTemplates
    # Verify scripts are shared by every experiment, so their templates are catalog-wide.
    verify: list[ScriptTemplateEntry]

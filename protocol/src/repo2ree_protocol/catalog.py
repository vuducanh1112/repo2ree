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
ReeStepStatus = Literal["complete", "ready", "blocked"]


class ReeStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: ReeStepKey
    order: int
    label: str
    requires: list[ReeStepKey] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)


class ReeStepState(ReeStep):
    status: ReeStepStatus


class ReeSteps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[ReeStepState] = Field(default_factory=list)
    next: ReeStepKey | None = None


class ScriptTemplateEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    description: str
    body: str
    is_default: bool


class ReservedScriptTemplates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    templates: list[ScriptTemplateEntry]


class ExperimentScriptTemplates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_pattern: str
    templates: list[ScriptTemplateEntry]


class ScriptTemplateCatalog(BaseModel):
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

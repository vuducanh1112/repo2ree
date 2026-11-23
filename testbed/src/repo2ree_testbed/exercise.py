from __future__ import annotations

import json
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from repo2ree_testbed.api_models import DefinitionPatch, ReviewBasis, ScriptKind, ScriptTarget
from repo2ree_testbed.showcases import ProjectName, RecipeScript

FORMAT: Final = "repo2ree-exercise/1"

Label = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,31}$")]
ExperimentName = Annotated[str, Field(min_length=1)]
SealSignature = Literal["valid", "foreign_key", "other_seal", "other_claim", "tampered"]
ReviewSignature = Literal["valid", "foreign_key", "other_seal", "other_record", "tampered"]
BundleCorruption = Literal["intact", "truncated", "unknown_head", "objects_removed", "file_changed", "foreign_commit"]
FaultKind = Literal["kill", "no_space", "history_locked"]
FaultPoint = Literal["pending", "executing", "completed"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Uploaded(_Model):
    kind: Literal["uploaded"] = "uploaded"
    project: ProjectName


class Fetched(_Model):
    kind: Literal["fetched"] = "fetched"
    origin_url: Annotated[str, Field(min_length=1)]
    source_type: Literal["git", "tarball", "zip"]
    revision: str = ""


class FromRecipe(_Model):
    kind: Literal["recipe"] = "recipe"
    project: ProjectName
    file: RecipeScript


class Text(_Model):
    kind: Literal["text"] = "text"
    text: str


type Source = Annotated[Uploaded | Fetched, Field(discriminator="kind")]
type ScriptContent = Annotated[FromRecipe | Text, Field(discriminator="kind")]


class _Step(_Model):
    ree: Label


class InitializeRee(_Step):
    operation: Literal["initialize_ree"] = "initialize_ree"
    name: Annotated[str, Field(min_length=1)] | None = None


class AcquireSource(_Step):
    operation: Literal["acquire_source"] = "acquire_source"
    source: Source


class RemoveSource(_Step):
    operation: Literal["remove_source"] = "remove_source"


class LoadReeBundle(_Step):
    operation: Literal["load_ree_bundle"] = "load_ree_bundle"
    exported_by: Label
    corruption: BundleCorruption = Field(default="intact", exclude_if=lambda corruption: corruption == "intact")


class PatchReeDefinition(_Step):
    operation: Literal["patch_ree_definition"] = "patch_ree_definition"
    patch: DefinitionPatch


class WriteScript(_Step):
    operation: Literal["write_script"] = "write_script"
    script: ScriptKind
    experiment: ExperimentName | None = None
    content: ScriptContent

    @model_validator(mode="after")
    def _experiment_iff_an_experiment_s_script(self) -> Self:
        per_experiment = self.script in {"experiment_run", "experiment_verify"}
        if per_experiment != (self.experiment is not None):
            raise ValueError(f"a {self.script} script {'names' if per_experiment else 'names no'} experiment")
        return self


class SuggestScripts(_Step):
    operation: Literal["suggest_scripts"] = "suggest_scripts"
    targets: tuple[ScriptTarget, ...] = Field(min_length=1)


class LintScripts(_Step):
    operation: Literal["lint_scripts"] = "lint_scripts"
    targets: tuple[ScriptTarget, ...] = Field(min_length=1)


class EvaluateReproducibility(_Step):
    operation: Literal["evaluate_reproducibility"] = "evaluate_reproducibility"
    strict: bool = False


class ObserveHardware(_Step):
    operation: Literal["observe_hardware"] = "observe_hardware"


class CheckWorkingEnvironment(_Step):
    operation: Literal["check_working_environment"] = "check_working_environment"


class MaterializeWorkspace(_Step):
    operation: Literal["materialize_workspace"] = "materialize_workspace"


class BuildExperimentEnvironment(_Step):
    operation: Literal["build_experiment_environment"] = "build_experiment_environment"


class GenerateSbom(_Step):
    operation: Literal["generate_sbom"] = "generate_sbom"


class CrossCheckSbom(_Step):
    operation: Literal["cross_check_sbom"] = "cross_check_sbom"


class ActivateExperimentEnvironment(_Step):
    operation: Literal["activate_experiment_environment"] = "activate_experiment_environment"


class RunExperiment(_Step):
    operation: Literal["run_experiment"] = "run_experiment"
    experiment: ExperimentName


class SealRee(_Step):
    operation: Literal["seal_ree"] = "seal_ree"
    source_included: bool = True
    experiment_environment_included: bool = True
    results_included: bool = True


class SignRee(_Step):
    operation: Literal["sign_ree"] = "sign_ree"
    claim: Literal["author_approval"] = "author_approval"
    signature: SealSignature = "valid"


class ReviewAcquireSource(_Step):
    operation: Literal["review_acquire_source"] = "review_acquire_source"
    review: Label
    basis: ReviewBasis = "auto"


class ReviewBuildExperimentEnvironment(_Step):
    operation: Literal["review_build_experiment_environment"] = "review_build_experiment_environment"
    review: Label
    basis: ReviewBasis = "auto"


class ReviewActivateExperimentEnvironment(_Step):
    operation: Literal["review_activate_experiment_environment"] = "review_activate_experiment_environment"
    review: Label


class ReviewRunExperiment(_Step):
    operation: Literal["review_run_experiment"] = "review_run_experiment"
    review: Label
    experiment: ExperimentName


class SignReview(_Step):
    operation: Literal["sign_review"] = "sign_review"
    review: Label
    signature: ReviewSignature = "valid"


type Step = Annotated[
    InitializeRee
    | AcquireSource
    | RemoveSource
    | LoadReeBundle
    | PatchReeDefinition
    | WriteScript
    | SuggestScripts
    | LintScripts
    | EvaluateReproducibility
    | ObserveHardware
    | CheckWorkingEnvironment
    | MaterializeWorkspace
    | BuildExperimentEnvironment
    | GenerateSbom
    | CrossCheckSbom
    | ActivateExperimentEnvironment
    | RunExperiment
    | SealRee
    | SignRee
    | ReviewAcquireSource
    | ReviewBuildExperimentEnvironment
    | ReviewActivateExperimentEnvironment
    | ReviewRunExperiment
    | SignReview,
    Field(discriminator="operation"),
]


class Fault(_Model):
    step: NonNegativeInt
    kind: FaultKind
    at: FaultPoint


FilePart = Literal["overlay", "records"]
FileChange = Literal["write", "append", "remove", "mode", "add"]
HistoryChange = Literal["commit", "reset", "amend"]


class _Drift(_Model):
    before: NonNegativeInt
    ree: Label
    review: Label | None = None


class FileDrift(_Drift):
    kind: Literal["file"] = "file"
    part: FilePart
    change: FileChange
    pick: NonNegativeInt = 0

    @model_validator(mode="after")
    def _added_where_a_file_is_the_ree_s(self) -> Self:
        if self.part != "overlay" and self.change == "add":
            raise ValueError(f"a file added beside the {self.part} is none of the REE's: add one to the overlay")
        return self


class HistoryDrift(_Drift):
    kind: Literal["history"] = "history"
    change: HistoryChange
    until: NonNegativeInt

    @model_validator(mode="after")
    def _undone_after_it_arose(self) -> Self:
        if self.until <= self.before:
            raise ValueError(f"a history drift before step {self.before} is put back before step {self.until}")
        return self


class RevertedDrift(_Drift):
    kind: Literal["reverted"] = "reverted"
    part: FilePart
    change: FileChange
    pick: NonNegativeInt = 0

    @model_validator(mode="after")
    def _added_where_a_file_is_the_ree_s(self) -> Self:
        if self.part != "overlay" and self.change == "add":
            raise ValueError(f"a file added beside the {self.part} is none of the REE's: add one to the overlay")
        return self


class ReflogDrift(_Drift):
    kind: Literal["reflog"] = "reflog"


type Drift = Annotated[FileDrift | HistoryDrift | RevertedDrift | ReflogDrift, Field(discriminator="kind")]


class Exercise(_Model):
    format: Literal["repo2ree-exercise/1"] = FORMAT
    rees: tuple[Label, ...] = Field(min_length=1)
    steps: tuple[Step, ...]
    faults: tuple[Fault, ...] = ()
    drifts: tuple[Drift, ...] = ()

    @model_validator(mode="after")
    def _every_name_is_the_exercise_s(self) -> Self:
        problems = [f"{label} is named twice" for label in sorted(set(self.rees)) if self.rees.count(label) > 1]
        known = set(self.rees)
        for index, step in enumerate(self.steps):
            if step.ree not in known:
                problems.append(f"step {index} runs in {step.ree}, which the exercise does not name")
            if isinstance(step, LoadReeBundle) and step.exported_by not in known - {step.ree}:
                problems.append(f"step {index} loads what {step.exported_by} exports, which is no other REE here")
        faulted = [fault.step for fault in self.faults]
        problems += [f"fault at step {index}, which is no step" for index in faulted if index >= len(self.steps)]
        problems += [f"step {index} has two faults" for index in sorted(set(faulted)) if faulted.count(index) > 1]
        for drift in self.drifts:
            initialized = self.initialized(drift.ree)
            if drift.ree not in known:
                problems.append(f"a drift in {drift.ree}, which the exercise does not name")
            elif drift.before > len(self.steps):
                problems.append(f"a drift before step {drift.before}, which is no step")
            elif initialized is None or drift.before <= initialized:
                problems.append(f"a drift in {drift.ree} before step {drift.before}, before any step initialized it")
            elif isinstance(drift, HistoryDrift) and drift.until > len(self.steps):
                problems.append(f"a drift put back before step {drift.until}, which is no step")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def initialized(self, ree: Label) -> int | None:
        return next(
            (index for index, step in enumerate(self.steps) if isinstance(step, InitializeRee) and step.ree == ree),
            None,
        )


def schema_document() -> str:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:repo2ree:exercise:1",
        **Exercise.model_json_schema(),
    }
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"

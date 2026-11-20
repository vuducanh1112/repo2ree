"""An exercise: one replayable input to the domain, as ``contracts/exercise/exercise.schema.json`` publishes it.

An exercise names the REEs it works in, the operations it runs in each, in order, the faults it injects at
some of them, and the files that drift between them: changed outside ree, as an editor, a disk or another program
changes one. It says what goes in, never how: a source, a script or a signature is named as a fixture or as
another REE's export, and replay turns it into whatever the surface it runs on takes. Every operation is spelled
by its name in the specification's catalogue, and nothing in an exercise names this implementation.

An exercise is any such sequence, a refused one included: whether an operation should succeed is the
specification's to judge from the trace, not the exercise's to know.
"""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from repo2ree_testbed.api_models import DefinitionPatch, ReviewBasis, ScriptKind, ScriptTarget
from repo2ree_testbed.showcases import ProjectName, RecipeScript

FORMAT: Final = "repo2ree-exercise/1"

Label = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,31}$")]
ExperimentName = Annotated[str, Field(min_length=1)]
# How replay makes a signature over what the step signs: as a signer would, or wrong in one named way.
SealSignature = Literal["valid", "foreign_key", "other_seal", "other_claim", "tampered"]
ReviewSignature = Literal["valid", "foreign_key", "other_seal", "other_record", "tampered"]
FaultKind = Literal["kill", "no_space", "history_locked"]
# Where in a step's attempt a fault lands: each state the specification gives an attempt before it settles.
FaultPoint = Literal["pending", "executing", "completed"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ---- What goes in --------------------------------------------------------------------------------------------


class Uploaded(_Model):
    """A project's source, packed as an upload."""

    kind: Literal["uploaded"] = "uploaded"
    project: ProjectName


class Fetched(_Model):
    """A source fetched from its origin."""

    kind: Literal["fetched"] = "fetched"
    origin_url: Annotated[str, Field(min_length=1)]
    source_type: Literal["git", "tarball", "zip"]
    revision: str = ""


class FromRecipe(_Model):
    """A script as a project's recipe writes it."""

    kind: Literal["recipe"] = "recipe"
    project: ProjectName
    file: RecipeScript


class Text(_Model):
    """A script given whole."""

    kind: Literal["text"] = "text"
    text: str


type Source = Annotated[Uploaded | Fetched, Field(discriminator="kind")]
type ScriptContent = Annotated[FromRecipe | Text, Field(discriminator="kind")]


# ---- Steps, one per catalogued operation -----------------------------------------------------------------------


class _Step(_Model):
    ree: Label


class InitializeRee(_Step):
    """Make the REE: until a step does, it does not exist."""

    operation: Literal["initialize_ree"] = "initialize_ree"
    # The name the REE declares itself by; the exercise's label for it when none is given.
    name: Annotated[str, Field(min_length=1)] | None = None


class AcquireSource(_Step):
    operation: Literal["acquire_source"] = "acquire_source"
    source: Source


class RemoveSource(_Step):
    operation: Literal["remove_source"] = "remove_source"


class LoadReeBundle(_Step):
    """Load what another REE of the exercise exports, as it stands at this step."""

    operation: Literal["load_ree_bundle"] = "load_ree_bundle"
    exported_by: Label


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
    """Open the review the exercise calls ``review``, or open it afresh."""

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


# ---- Faults and the exercise ---------------------------------------------------------------------------------


class Fault(_Model):
    """A fault injected into one step's attempt once it reaches ``at``: the process that runs it killed there, or
    from there on its disk full or its REE's history locked by another."""

    step: NonNegativeInt
    kind: FaultKind
    at: FaultPoint


def _inside_the_ree(path: str) -> str:
    parts = PurePosixPath(path).parts
    if not parts or path.startswith("/") or ".." in parts or parts[0] == ".git":
        raise ValueError(f"{path} is no file of an REE: a path from it, inside it, never its .git")
    return path


# A file by its path from its REE: relative, inside the REE, and never the REE's own version storage.
ReePath = Annotated[str, AfterValidator(_inside_the_ree)]


class Drift(_Model):
    """A file of an REE changed outside ree before step ``before``: written with ``content``, or removed without.
    ``before`` may be the number of steps, for a drift after the last. Only an REE a step has initialized drifts:
    before that, its files are what initializing it starts from, which is no change of what it records."""

    before: NonNegativeInt
    ree: Label
    path: ReePath
    content: str | None = None


class Exercise(_Model):
    """The REEs it names, none of which exists until a step initializes it, the steps run in them in order, the
    faults, and the drifts."""

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
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def initialized(self, ree: Label) -> int | None:
        """The step that first initializes ``ree``; None when no step does."""
        return next(
            (index for index, step in enumerate(self.steps) if isinstance(step, InitializeRee) and step.ree == ree),
            None,
        )


def schema_document() -> str:
    """The exercise format as ``contracts/exercise/exercise.schema.json`` publishes it."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:repo2ree:exercise:1",
        **Exercise.model_json_schema(),
    }
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"

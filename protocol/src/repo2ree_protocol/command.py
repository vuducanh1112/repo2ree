from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from repo2ree_protocol.argv import POSITIONAL, STDIN
from repo2ree_ree.review import ReviewLaunch
from repo2ree_ree.signature import SignatureClaim

OperationName = Literal[
    "initialize_ree",
    "acquire_source",
    "remove_source",
    "load_ree_bundle",
    "patch_ree_definition",
    "write_script",
    "suggest_scripts",
    "lint_scripts",
    "evaluate_reproducibility",
    "observe_hardware",
    "check_working_environment",
    "materialize_workspace",
    "build_experiment_environment",
    "generate_sbom",
    "cross_check_sbom",
    "activate_experiment_environment",
    "run_experiment",
    "seal_ree",
    "sign_ree",
    "sign_review",
    "review_acquire_source",
    "review_build_experiment_environment",
    "review_activate_experiment_environment",
    "review_run_experiment",
]

ReviewBasis = Literal["auto", "independent", "bundled"]


class ReviewAcquireSourceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review, an attempt of its own beside the REE.")]
    basis: ReviewBasis = Field(
        default="auto",
        description="independent fetches the recorded origin; bundled extracts the REE's own snapshot; "
        "auto takes independent where the REE allows it.",
    )
    launch: ReviewLaunch = Field(
        default_factory=ReviewLaunch,
        description="How every script of the review is launched: the author's launch with the reviewer's options, "
        "or natively.",
    )


class ReviewAcquireSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["review_acquire_source"] = "review_acquire_source"
    args: ReviewAcquireSourceArgs


class ReviewBuildExperimentEnvironmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review, an attempt of its own beside the REE.")]
    basis: ReviewBasis = Field(
        default="auto",
        description="independent runs the author's build over the review's source; bundled certifies the "
        "experiment environment the REE ships; auto takes independent where it can.",
    )


class ReviewBuildExperimentEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["review_build_experiment_environment"] = "review_build_experiment_environment"
    args: ReviewBuildExperimentEnvironmentArgs


class ReviewActivateExperimentEnvironmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review, an attempt of its own beside the REE.")]


class ReviewActivateExperimentEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["review_activate_experiment_environment"] = "review_activate_experiment_environment"
    args: ReviewActivateExperimentEnvironmentArgs


class ReviewRunExperimentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review, an attempt of its own beside the REE.")]
    experiment_name: Annotated[str, POSITIONAL, Field(description="The experiment to reproduce.")]


class ReviewRunExperimentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["review_run_experiment"] = "review_run_experiment"
    args: ReviewRunExperimentArgs


class MaterializeWorkspaceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MaterializeWorkspaceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["materialize_workspace"] = "materialize_workspace"
    args: MaterializeWorkspaceArgs = MaterializeWorkspaceArgs()


class AcquireSourceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["download", "upload"] = Field(
        description="download fetches --origin-url; upload takes an archive staged in the REE."
    )
    origin_url: str = Field(default="", description="Where to download the source from.")
    source_type: Literal["git", "tarball", "zip"] | None = Field(
        default=None, description="What the origin serves; by default read off the URL."
    )
    revision: str = Field(default="", description="The git commit, branch or tag; by default the origin's HEAD.")
    upload_token: str = Field(default="", description="The staged archive's token.")
    archive_name: str = Field(default="", description="The staged archive's file name.")


class AcquireSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["acquire_source"] = "acquire_source"
    args: AcquireSourceArgs


class LoadReeBundleArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_token: str = Field(description="The staged bundle's token.")
    archive_name: str = Field(description="The staged bundle's file name.")


class LoadReeBundleCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["load_ree_bundle"] = "load_ree_bundle"
    args: LoadReeBundleArgs


class WriteScriptArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Annotated[str, POSITIONAL, Field(description="The script's path in the REE, or its KIND[:EXPERIMENT].")]
    content: Annotated[str, STDIN, Field(description="The script.")]
    expected_etag: str = Field(
        default="",
        description="Write only if the script is still this digest (sha256:...), as `ree status` reports it.",
    )


class WriteScriptCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["write_script"] = "write_script"
    args: WriteScriptArgs


class PatchReeDefinitionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patch: Annotated[dict[str, Any], STDIN, Field(description="The definition's top-level fields to replace, as JSON.")]
    expected_version: str = Field(
        default="", description="Change only if the REE is still at this revision, as `ree status` reports it."
    )


class PatchReeDefinitionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["patch_ree_definition"] = "patch_ree_definition"
    args: PatchReeDefinitionArgs


class RemoveSourceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RemoveSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["remove_source"] = "remove_source"
    args: RemoveSourceArgs = RemoveSourceArgs()


class BuildExperimentEnvironmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as for a fresh run of a stochastic experiment.",
    )


class BuildExperimentEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["build_experiment_environment"] = "build_experiment_environment"
    args: BuildExperimentEnvironmentArgs = BuildExperimentEnvironmentArgs()


class GenerateSbomArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as to check a scanner's answer again.",
    )


class GenerateSbomCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["generate_sbom"] = "generate_sbom"
    args: GenerateSbomArgs = GenerateSbomArgs()


class CrossCheckSbomArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CrossCheckSbomCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["cross_check_sbom"] = "cross_check_sbom"
    args: CrossCheckSbomArgs = CrossCheckSbomArgs()


class EvaluateReproducibilityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict: bool = Field(default=False, description="Count an unpinned dependency as a failure.")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as after the analyzer itself changed.",
    )


class EvaluateReproducibilityCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["evaluate_reproducibility"] = "evaluate_reproducibility"
    args: EvaluateReproducibilityArgs = EvaluateReproducibilityArgs()


class RunExperimentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_name: Annotated[str, POSITIONAL, Field(description="The experiment, as the definition names it.")]
    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as for a fresh run of a stochastic experiment.",
    )


class RunExperimentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["run_experiment"] = "run_experiment"
    args: RunExperimentArgs


class ObserveHardwareArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObserveHardwareCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["observe_hardware"] = "observe_hardware"
    args: ObserveHardwareArgs = ObserveHardwareArgs()


class ActivateExperimentEnvironmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as for a fresh run of a stochastic experiment.",
    )


class ActivateExperimentEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["activate_experiment_environment"] = "activate_experiment_environment"
    args: ActivateExperimentEnvironmentArgs = ActivateExperimentEnvironmentArgs()


class CheckWorkingEnvironmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as for a fresh run of a stochastic experiment.",
    )


class CheckWorkingEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["check_working_environment"] = "check_working_environment"
    args: CheckWorkingEnvironmentArgs = CheckWorkingEnvironmentArgs()


TargetKind = Literal[
    "build_experiment_environment",
    "activate_experiment_environment",
    "experiment_run",
    "experiment_verify",
    "launch",
    "check_working_environment",
]


class ScriptTargetSelectorArg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    experiment_name: str | None = None

    @model_validator(mode="after")
    def _named_only_for_experiments(self) -> ScriptTargetSelectorArg:
        if self.kind in ("experiment_run", "experiment_verify"):
            if not self.experiment_name:
                raise ValueError(f"{self.kind} requires an experiment_name")
        elif self.experiment_name:
            raise ValueError(f"{self.kind} must not carry an experiment_name")
        return self


class ScriptTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    experiment_name: str | None = None
    path: str


class SuggestScriptsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[ScriptTargetSelectorArg] = Field(description="The scripts to propose, each KIND[:EXPERIMENT].")


class SuggestScriptsCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["suggest_scripts"] = "suggest_scripts"
    args: SuggestScriptsArgs


class LintScriptsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[ScriptTargetSelectorArg] = Field(description="The scripts to check, each KIND[:EXPERIMENT].")


class LintScriptsCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["lint_scripts"] = "lint_scripts"
    args: LintScriptsArgs


class SealReeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_included: bool = Field(default=True, description="Carry the source snapshot.")
    experiment_environment_included: bool = Field(default=True, description="Carry the experiment environment.")
    results_included: bool = Field(default=True, description="Carry the experiments' results.")


class SealReeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["seal_ree"] = "seal_ree"
    args: SealReeArgs = SealReeArgs()


class SignReeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: SignatureClaim = Field(default="author_approval", description="What the signature claims.")
    upload_token: str = Field(description="The staged bundle's token.")
    archive_name: str = Field(description="The staged bundle's file name.")


class SignReeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["sign_ree"] = "sign_ree"
    args: SignReeArgs


class SignReviewArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review to sign.")]
    upload_token: str = Field(description="The staged bundle's token.")
    archive_name: str = Field(description="The staged bundle's file name.")


class SignReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["sign_review"] = "sign_review"
    args: SignReviewArgs


Command = Annotated[
    ReviewAcquireSourceCommand
    | ReviewBuildExperimentEnvironmentCommand
    | ReviewActivateExperimentEnvironmentCommand
    | ReviewRunExperimentCommand
    | MaterializeWorkspaceCommand
    | AcquireSourceCommand
    | LoadReeBundleCommand
    | WriteScriptCommand
    | PatchReeDefinitionCommand
    | RemoveSourceCommand
    | BuildExperimentEnvironmentCommand
    | GenerateSbomCommand
    | CrossCheckSbomCommand
    | EvaluateReproducibilityCommand
    | RunExperimentCommand
    | ObserveHardwareCommand
    | ActivateExperimentEnvironmentCommand
    | CheckWorkingEnvironmentCommand
    | SuggestScriptsCommand
    | LintScriptsCommand
    | SealReeCommand
    | SignReeCommand
    | SignReviewCommand,
    Field(discriminator="operation"),
]

command_adapter: TypeAdapter[Command] = TypeAdapter(Command)

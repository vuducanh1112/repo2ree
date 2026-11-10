"""The shared runtime-contract subgraph checks.

Activation and experiment inference both begin from the resolved logical project
root and the current ``ReeDefinition.runtime`` and resolve it into a typed experiment environment
contract before any command strategy runs. They never scan for arbitrary tar
files: the declared path is the only experiment environment, and it is either inspected as a
built artifact or matched against an unchanged generated build.

Every blocking condition is emitted as a check warning and routed (in the DAG)
straight to a ``not_inferred`` result, so the target's trace explains exactly
why no experiment environment contract was established.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import ClassVar

from repo2ree_core.author_recipes.inference.artifact_inspection import (
    DockerArchiveInspection,
    VenvArchiveInspection,
    inspect_experiment_environment_artifact,
)
from repo2ree_core.author_recipes.inference.build_regeneration import expected_builds_for_experiment_environment
from repo2ree_core.author_recipes.inference.models import BindingKind, CheckResult, DecisionContext
from repo2ree_core.author_recipes.inference.naming import venv_build_dir
from repo2ree_core.author_recipes.inference.warnings import make_warning
from repo2ree_protocol.inference import (
    DockerExperimentEnvironmentContract,
    ExperimentEnvironmentContractBinding,
    ExperimentEnvironmentContractObservation,
    ExperimentEnvironmentDeclarationBinding,
    ImageCommandBinding,
    ProjectRootBinding,
    VenvExperimentEnvironmentContract,
)
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.paths import validate_relative_path
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT


def _declared_path(context: DecisionContext) -> str | None:
    raw = context.experiment_environment.declared_experiment_environment_path
    return raw or None


def _require_declaration(context: DecisionContext) -> ExperimentEnvironmentDeclarationBinding:
    binding = context.binding("experiment_environment_declaration")
    if not isinstance(binding, ExperimentEnvironmentDeclarationBinding):
        raise ValueError("runtime-artifact check reached without a experiment_environment_declaration binding")
    return binding


class DeclaredExperimentEnvironmentPathCheck:
    code = "declared_experiment_environment_path"
    label = "Is an experiment environment artifact declared, inside the logical project root?"
    branches = frozenset({"absent", "outside_root", "valid"})
    requires: frozenset[BindingKind] = frozenset({"project_root"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "absent": frozenset(),
        "outside_root": frozenset(),
        "valid": frozenset({"experiment_environment_declaration"}),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        root = context.binding("project_root")
        if not isinstance(root, ProjectRootBinding):
            raise ValueError("declared_experiment_environment_path check reached without a project_root binding")

        declared = _declared_path(context)
        if declared is None:
            return CheckResult(
                branch="absent",
                observed=ExperimentEnvironmentContractObservation(
                    result="absent", detail="no experiment environment declared on the REE"
                ),
                warnings=[make_warning("experiment_environment_declaration_missing")],
            )

        if not _within_project_root(declared, root.path):
            return CheckResult(
                branch="outside_root",
                observed=ExperimentEnvironmentContractObservation(
                    result="outside_root",
                    detail=f"declared experiment environment {declared!r} escapes the project root",
                ),
                warnings=[make_warning("experiment_environment_outside_project_root", affected_paths=[declared])],
            )

        stat = context.experiment_environment.accessor.stat(declared)
        binding = ExperimentEnvironmentDeclarationBinding(path=declared, digest=stat.digest)
        return CheckResult(
            branch="valid",
            observed=ExperimentEnvironmentContractObservation(result="valid", detail=declared),
            bindings=(binding,),
        )


class ExperimentEnvironmentArtifactStateCheck:
    code = "experiment_environment_artifact_state"
    label = "Does the declared experiment environment artifact exist as a file yet?"
    branches = frozenset({"regular_file", "missing"})
    requires: frozenset[BindingKind] = frozenset({"experiment_environment_declaration"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "regular_file": frozenset(),
        "missing": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        declaration = _require_declaration(context)
        stat = context.experiment_environment.accessor.stat(declaration.path)
        branch = "regular_file" if (stat.exists and stat.is_file) else "missing"
        return CheckResult(
            branch=branch,
            observed=ExperimentEnvironmentContractObservation(result=branch, detail=declaration.path),
        )


class ExperimentEnvironmentArtifactInspectionCheck:
    code = "inspect_experiment_environment_artifact"
    label = "What experiment environment does the built artifact declare?"
    branches = frozenset({"docker_single_ref", "docker_multiple_refs", "docker_no_ref", "venv", "invalid"})
    requires: frozenset[BindingKind] = frozenset({"experiment_environment_declaration"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "docker_single_ref": frozenset({"experiment_environment_contract", "image_command"}),
        "docker_multiple_refs": frozenset(),
        "docker_no_ref": frozenset(),
        "venv": frozenset({"experiment_environment_contract"}),
        "invalid": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        declaration = _require_declaration(context)
        stream = context.experiment_environment.accessor.open(declaration.path)
        if stream is None:
            return CheckResult(
                branch="invalid",
                observed=ExperimentEnvironmentContractObservation(
                    result="invalid", detail="experiment environment artifact unreadable"
                ),
                warnings=[make_warning("experiment_environment_archive_invalid", affected_paths=[declaration.path])],
            )
        try:
            inspection = inspect_experiment_environment_artifact(stream)
        finally:
            stream.close()

        if isinstance(inspection, VenvArchiveInspection):
            assumed = inspection.restore_dir is None
            venv_contract = VenvExperimentEnvironmentContract(
                artifact_path=declaration.path,
                venv_restore_dir=inspection.restore_dir or venv_build_dir(context.ree_name),
            )
            return CheckResult(
                branch="venv",
                observed=ExperimentEnvironmentContractObservation(
                    result="venv",
                    experiment_environment_kind="venv_archive",
                    provenance="inspected_artifact",
                    detail=f"restore to {venv_contract.venv_restore_dir}" + (" (assumed default)" if assumed else ""),
                ),
                bindings=(
                    ExperimentEnvironmentContractBinding(contract=venv_contract, provenance="inspected_artifact"),
                ),
                warnings=(
                    [make_warning("venv_restore_dir_assumed", affected_paths=[declaration.path])] if assumed else []
                ),
            )

        if isinstance(inspection, DockerArchiveInspection):
            refs = inspection.repo_tags
            if len(refs) == 0:
                return CheckResult(
                    branch="docker_no_ref",
                    observed=ExperimentEnvironmentContractObservation(
                        result="docker_no_ref",
                        experiment_environment_kind="docker_archive",
                        detail="no usable RepoTags",
                    ),
                    warnings=[
                        make_warning("experiment_environment_image_ref_missing", affected_paths=[declaration.path])
                    ],
                )
            if len(refs) > 1:
                warning = make_warning("multiple_experiment_environment_images", affected_paths=[declaration.path])
                warning.details = {"image_refs": refs}
                return CheckResult(
                    branch="docker_multiple_refs",
                    observed=ExperimentEnvironmentContractObservation(
                        result="docker_multiple_refs",
                        experiment_environment_kind="docker_archive",
                        detail=", ".join(refs),
                    ),
                    warnings=[warning],
                )
            docker_contract = DockerExperimentEnvironmentContract(artifact_path=declaration.path, image_ref=refs[0])
            return CheckResult(
                branch="docker_single_ref",
                observed=ExperimentEnvironmentContractObservation(
                    result="docker_single_ref",
                    experiment_environment_kind="docker_archive",
                    provenance="inspected_artifact",
                    detail=refs[0],
                ),
                bindings=(
                    ExperimentEnvironmentContractBinding(contract=docker_contract, provenance="inspected_artifact"),
                    # The image's declared command travels forward so the
                    # command-candidate check need not re-open this archive.
                    ImageCommandBinding(argv=inspection.argv, shell_command=inspection.shell_command),
                ),
            )

        return CheckResult(
            branch="invalid",
            observed=ExperimentEnvironmentContractObservation(result="invalid", detail=inspection.reason),
            warnings=[make_warning("experiment_environment_archive_invalid", affected_paths=[declaration.path])],
        )


class UnchangedGeneratedBuildCheck:
    code = "unchanged_generated_build"
    label = "Would the current build script generate this experiment environment?"
    branches = frozenset({"matched", "unmatched"})
    requires: frozenset[BindingKind] = frozenset({"experiment_environment_declaration"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "matched": frozenset({"experiment_environment_contract"}),
        "unmatched": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        declaration = _require_declaration(context)
        # Several strategies can be viable at once (a repo carrying both a
        # Dockerfile and a requirements.txt), and they all write to the declared
        # path now — so the written script's digest, not its artifact path, is
        # what says which one the author settled on.
        for expected in expected_builds_for_experiment_environment(context, declaration.path):
            if not _written_build_matches(context, expected.body):
                continue
            return CheckResult(
                branch="matched",
                observed=ExperimentEnvironmentContractObservation(
                    result="matched",
                    experiment_environment_kind=expected.contract.kind,
                    provenance="unchanged_generated_build",
                    detail=declaration.path,
                ),
                bindings=(
                    ExperimentEnvironmentContractBinding(
                        contract=expected.contract, provenance="unchanged_generated_build"
                    ),
                ),
            )
        return CheckResult(
            branch="unmatched",
            observed=ExperimentEnvironmentContractObservation(result="unmatched", detail=declaration.path),
            warnings=[
                make_warning("experiment_environment_artifact_missing", affected_paths=[declaration.path]),
                make_warning("experiment_environment_not_resolved"),
            ],
        )


def _written_build_matches(context: DecisionContext, expected_body: str) -> bool:
    stat = context.experiment_environment.accessor.stat(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT)
    if not stat.exists or not stat.is_file or stat.digest is None:
        return False
    expected_digest = digest_bytes(expected_body.encode())
    return stat.digest == expected_digest


class ExperimentEnvironmentContractKindCheck:
    """Routes a command branch by the resolved contract's experiment environment kind.

    Both the docker and the venv command strategy branch start with this so each
    proceeds only for its own kind and declines (``not_applicable``) for the
    other — exactly one kind is ever resolved, so exactly one branch is viable.
    """

    code = "experiment_environment_contract_kind"
    label = "What kind of experiment environment was resolved?"
    branches = frozenset({"docker", "venv"})
    requires: frozenset[BindingKind] = frozenset({"experiment_environment_contract"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {"docker": frozenset(), "venv": frozenset()}

    def evaluate(self, context: DecisionContext) -> CheckResult:
        binding = context.binding("experiment_environment_contract")
        if not isinstance(binding, ExperimentEnvironmentContractBinding):
            raise ValueError(
                "experiment_environment_contract_kind check reached without a experiment_environment_contract binding"
            )
        kind = binding.contract.kind
        branch = "docker" if kind == "docker_archive" else "venv"
        return CheckResult(
            branch=branch,
            observed=ExperimentEnvironmentContractObservation(
                result=branch, experiment_environment_kind=kind, provenance=binding.provenance
            ),
        )


def _within_project_root(declared: str, project_root: str) -> bool:
    try:
        validate_relative_path(declared)
    except (ValueError, TypeError):
        return False
    if project_root == ".":
        return True
    try:
        PurePosixPath(declared).relative_to(PurePosixPath(project_root))
    except ValueError:
        return False
    return True

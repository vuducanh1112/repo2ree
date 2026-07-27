"""The shared runtime-contract subgraph checks.

Activation and experiment inference both begin from the resolved logical project
root and the current ``ReeIntent.runtime`` and resolve it into a typed runtime
contract before any command strategy runs. They never scan for arbitrary tar
files: the declared path is the only runtime, and it is either inspected as a
built artifact or matched against an unchanged generated build.

Every blocking condition is emitted as a check warning and routed (in the DAG)
straight to a ``not_inferred`` result, so the target's trace explains exactly
why no runtime contract was established.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from repo2ree_core.authoring.script_inference.artifact_inspection import (
    DockerArchiveInspection,
    VenvArchiveInspection,
    inspect_runtime_artifact,
)
from repo2ree_core.authoring.script_inference.build_regeneration import expected_build_for_runtime
from repo2ree_core.authoring.script_inference.models import (
    DEFAULT_VENV_RESTORE_DIR,
    BindingKind,
    CheckResult,
    DecisionContext,
    DockerRuntimeContract,
    ImageCommandBinding,
    ProjectRootBinding,
    RuntimeContractBinding,
    RuntimeContractObservation,
    RuntimeDeclarationBinding,
    VenvRuntimeContract,
)
from repo2ree_core.authoring.script_inference.warnings import make_warning
from repo2ree_core.digests import digest_bytes
from repo2ree_core.path_safety import validate_relative_path
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT


def _declared_path(context: DecisionContext) -> str | None:
    raw = context.runtime.declared_runtime_path
    return raw or None


def _require_declaration(context: DecisionContext) -> RuntimeDeclarationBinding:
    binding = context.binding("runtime_declaration")
    if not isinstance(binding, RuntimeDeclarationBinding):
        raise ValueError("runtime-artifact check reached without a runtime_declaration binding")
    return binding


class DeclaredRuntimePathCheck:
    code = "declared_runtime_path"
    label = "Is a runtime artifact declared, inside the logical project root?"
    branches = frozenset({"absent", "outside_root", "valid"})
    requires: frozenset[BindingKind] = frozenset({"project_root"})
    produces: dict[str, frozenset[BindingKind]] = {
        "absent": frozenset(),
        "outside_root": frozenset(),
        "valid": frozenset({"runtime_declaration"}),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        root = context.binding("project_root")
        if not isinstance(root, ProjectRootBinding):
            raise ValueError("declared_runtime_path check reached without a project_root binding")

        declared = _declared_path(context)
        if declared is None:
            return CheckResult(
                branch="absent",
                observed=RuntimeContractObservation(result="absent", detail="no runtime declared on the REE"),
                warnings=[make_warning("runtime_declaration_missing")],
            )

        if not _within_project_root(declared, root.path):
            return CheckResult(
                branch="outside_root",
                observed=RuntimeContractObservation(
                    result="outside_root", detail=f"declared runtime {declared!r} escapes the project root"
                ),
                warnings=[make_warning("runtime_outside_project_root", affected_paths=[declared])],
            )

        stat = context.runtime.accessor.stat(declared)
        binding = RuntimeDeclarationBinding(path=declared, digest=stat.digest)
        return CheckResult(
            branch="valid",
            observed=RuntimeContractObservation(result="valid", detail=declared),
            bindings=(binding,),
        )


class RuntimeArtifactStateCheck:
    code = "runtime_artifact_state"
    label = "Does the declared runtime artifact exist as a file yet?"
    branches = frozenset({"regular_file", "missing"})
    requires: frozenset[BindingKind] = frozenset({"runtime_declaration"})
    produces: dict[str, frozenset[BindingKind]] = {
        "regular_file": frozenset(),
        "missing": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        declaration = _require_declaration(context)
        stat = context.runtime.accessor.stat(declaration.path)
        branch = "regular_file" if (stat.exists and stat.is_file) else "missing"
        return CheckResult(
            branch=branch,
            observed=RuntimeContractObservation(result=branch, detail=declaration.path),
        )


class RuntimeArtifactInspectionCheck:
    code = "inspect_runtime_artifact"
    label = "What runtime does the built artifact declare?"
    branches = frozenset({"docker_single_ref", "docker_multiple_refs", "docker_no_ref", "venv", "invalid"})
    requires: frozenset[BindingKind] = frozenset({"runtime_declaration"})
    produces: dict[str, frozenset[BindingKind]] = {
        "docker_single_ref": frozenset({"runtime_contract", "image_command"}),
        "docker_multiple_refs": frozenset(),
        "docker_no_ref": frozenset(),
        "venv": frozenset({"runtime_contract"}),
        "invalid": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        declaration = _require_declaration(context)
        stream = context.runtime.accessor.open(declaration.path)
        if stream is None:
            return CheckResult(
                branch="invalid",
                observed=RuntimeContractObservation(result="invalid", detail="runtime artifact unreadable"),
                warnings=[make_warning("runtime_archive_invalid", affected_paths=[declaration.path])],
            )
        try:
            inspection = inspect_runtime_artifact(stream)
        finally:
            stream.close()

        if isinstance(inspection, VenvArchiveInspection):
            assumed = inspection.restore_dir is None
            venv_contract = VenvRuntimeContract(
                artifact_path=declaration.path,
                venv_restore_dir=inspection.restore_dir or DEFAULT_VENV_RESTORE_DIR,
            )
            return CheckResult(
                branch="venv",
                observed=RuntimeContractObservation(
                    result="venv",
                    runtime_kind="venv_archive",
                    provenance="inspected_artifact",
                    detail=f"restore to {venv_contract.venv_restore_dir}" + (" (assumed default)" if assumed else ""),
                ),
                bindings=(RuntimeContractBinding(contract=venv_contract, provenance="inspected_artifact"),),
                warnings=(
                    [make_warning("venv_restore_dir_assumed", affected_paths=[declaration.path])] if assumed else []
                ),
            )

        if isinstance(inspection, DockerArchiveInspection):
            refs = inspection.repo_tags
            if len(refs) == 0:
                return CheckResult(
                    branch="docker_no_ref",
                    observed=RuntimeContractObservation(
                        result="docker_no_ref", runtime_kind="docker_archive", detail="no usable RepoTags"
                    ),
                    warnings=[make_warning("runtime_image_ref_missing", affected_paths=[declaration.path])],
                )
            if len(refs) > 1:
                warning = make_warning("multiple_runtime_images", affected_paths=[declaration.path])
                warning.details = {"image_refs": refs}
                return CheckResult(
                    branch="docker_multiple_refs",
                    observed=RuntimeContractObservation(
                        result="docker_multiple_refs",
                        runtime_kind="docker_archive",
                        detail=", ".join(refs),
                    ),
                    warnings=[warning],
                )
            docker_contract = DockerRuntimeContract(artifact_path=declaration.path, image_ref=refs[0])
            return CheckResult(
                branch="docker_single_ref",
                observed=RuntimeContractObservation(
                    result="docker_single_ref",
                    runtime_kind="docker_archive",
                    provenance="inspected_artifact",
                    detail=refs[0],
                ),
                bindings=(
                    RuntimeContractBinding(contract=docker_contract, provenance="inspected_artifact"),
                    # The image's declared command travels forward so the
                    # command-candidate check need not re-open this archive.
                    ImageCommandBinding(argv=inspection.argv, shell_command=inspection.shell_command),
                ),
            )

        return CheckResult(
            branch="invalid",
            observed=RuntimeContractObservation(result="invalid", detail=inspection.reason),
            warnings=[make_warning("runtime_archive_invalid", affected_paths=[declaration.path])],
        )


class UnchangedGeneratedBuildCheck:
    code = "unchanged_generated_build"
    label = "Would the current build script generate this runtime?"
    branches = frozenset({"matched", "unmatched"})
    requires: frozenset[BindingKind] = frozenset({"runtime_declaration"})
    produces: dict[str, frozenset[BindingKind]] = {
        "matched": frozenset({"runtime_contract"}),
        "unmatched": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        declaration = _require_declaration(context)
        expected = expected_build_for_runtime(context, declaration.path)
        if expected is not None and _written_build_matches(context, expected.body):
            return CheckResult(
                branch="matched",
                observed=RuntimeContractObservation(
                    result="matched",
                    runtime_kind=expected.contract.kind,
                    provenance="unchanged_generated_build",
                    detail=declaration.path,
                ),
                bindings=(RuntimeContractBinding(contract=expected.contract, provenance="unchanged_generated_build"),),
            )
        return CheckResult(
            branch="unmatched",
            observed=RuntimeContractObservation(result="unmatched", detail=declaration.path),
            warnings=[
                make_warning("runtime_artifact_missing", affected_paths=[declaration.path]),
                make_warning("runtime_not_resolved"),
            ],
        )


def _written_build_matches(context: DecisionContext, expected_body: str) -> bool:
    stat = context.runtime.accessor.stat(RESERVED_BUILD_SCRIPT)
    if not stat.exists or not stat.is_file or stat.digest is None:
        return False
    expected_digest = digest_bytes(expected_body.encode())
    return stat.digest == expected_digest


class RuntimeContractKindCheck:
    """Routes a command branch by the resolved contract's runtime kind.

    Both the docker and the venv command strategy branch start with this so each
    proceeds only for its own kind and declines (``not_applicable``) for the
    other — exactly one kind is ever resolved, so exactly one branch is viable.
    """

    code = "runtime_contract_kind"
    label = "What kind of runtime was resolved?"
    branches = frozenset({"docker", "venv"})
    requires: frozenset[BindingKind] = frozenset({"runtime_contract"})
    produces: dict[str, frozenset[BindingKind]] = {"docker": frozenset(), "venv": frozenset()}

    def evaluate(self, context: DecisionContext) -> CheckResult:
        binding = context.binding("runtime_contract")
        if not isinstance(binding, RuntimeContractBinding):
            raise ValueError("runtime_contract_kind check reached without a runtime_contract binding")
        kind = binding.contract.kind
        branch = "docker" if kind == "docker_archive" else "venv"
        return CheckResult(
            branch=branch,
            observed=RuntimeContractObservation(result=branch, runtime_kind=kind, provenance=binding.provenance),
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

from __future__ import annotations

from repo2ree_core.analysis.sbom.cyclonedx import ObservedPackage
from repo2ree_core.analysis.sbom.equivalence import (
    PackageDelta,
    closure_verdict,
    compare_sbom_closures,
)
from repo2ree_ree.primitives import GitRevision
from repo2ree_ree.review import (
    ComparisonVerdict,
    EvidenceBasis,
    ExperimentComparison,
    ExperimentEnvironmentComparison,
    ExperimentEnvironmentVerdict,
    ExperimentVerdict,
    PackageDeltaRecord,
    SourceComparison,
)


def compare_source_swhids(
    expected: str,
    observed: str,
    *,
    basis: EvidenceBasis = "independent",
    expected_revision: GitRevision | None = None,
    observed_revision: GitRevision | None = None,
    history_failure: str | None = None,
) -> SourceComparison:
    normalized_expected = expected.strip() or None
    normalized_observed = observed.strip() or None
    commit_differs = expected_revision is not None and (
        history_failure is not None or observed_revision != expected_revision
    )
    verdict: ComparisonVerdict
    if normalized_expected is None or normalized_observed is None:
        verdict = "inconclusive"
    elif normalized_expected != normalized_observed or commit_differs:
        verdict = "different"
    else:
        verdict = "identical"
    return SourceComparison(
        basis=basis,
        expected_swhid=normalized_expected,
        observed_swhid=normalized_observed,
        expected_revision=expected_revision,
        observed_revision=observed_revision,
        history_failure=history_failure,
        verdict=verdict,
    )


def compare_build_experiment_environments(
    *,
    expected_artifact_digest: str | None,
    observed_artifact_digest: str | None,
    expected_packages: list[ObservedPackage],
    observed_packages: list[ObservedPackage],
    expected_sbom_digest: str | None = None,
    observed_sbom_digest: str | None = None,
    sbom_tool_version: str | None = None,
    basis: EvidenceBasis = "independent",
) -> ExperimentEnvironmentComparison:
    delta = compare_sbom_closures(expected_packages, observed_packages)
    if expected_artifact_digest and expected_artifact_digest == observed_artifact_digest:
        verdict: ExperimentEnvironmentVerdict = "identical"
    else:
        verdict = closure_verdict(delta)
    return ExperimentEnvironmentComparison(
        basis=basis,
        verdict=verdict,
        expected_artifact_digest=expected_artifact_digest,
        observed_artifact_digest=observed_artifact_digest,
        expected_sbom_digest=expected_sbom_digest,
        observed_sbom_digest=observed_sbom_digest,
        sbom_tool_version=sbom_tool_version,
        expected_package_total=delta.expected_total,
        observed_package_total=delta.observed_total,
        matched=delta.matched,
        missing_count=delta.missing_count,
        extra_count=delta.extra_count,
        version_mismatch_count=delta.version_mismatch_count,
        advisory_count=delta.advisory_count,
        missing=_delta_records(delta.missing),
        extra=_delta_records(delta.extra),
        version_mismatches=_delta_records(delta.version_mismatches),
        advisory=_delta_records(delta.advisory),
    )


def compare_experiment_results(
    *,
    experiment_name: str,
    basis: EvidenceBasis,
    verify_script_path: str,
    expected_verify_script_digest: str | None,
    verify_script_digest: str | None,
    expected_activate_experiment_environment_script_digest: str | None,
    activate_experiment_environment_script_digest: str | None,
    expected_verify_exit_code: int | None,
    observed_verify_exit_code: int | None,
    run_exit_code: int | None,
    expected_output_digest: str | None = None,
    observed_output_digest: str | None = None,
    experiment_environment_digest: str | None = None,
    expected_launch_script_digest: str | None = None,
    launch_script_digest: str | None = None,
) -> ExperimentComparison:
    if (
        expected_verify_exit_code is None
        or expected_verify_script_digest is None
        or verify_script_digest is None
        or expected_verify_script_digest != verify_script_digest
        or expected_activate_experiment_environment_script_digest is None
        or expected_activate_experiment_environment_script_digest != activate_experiment_environment_script_digest
        or expected_verify_exit_code != 0
    ):
        verdict: ExperimentVerdict = "inconclusive"
    elif observed_verify_exit_code != 0:
        verdict = "different"
    elif expected_output_digest is not None and expected_output_digest == observed_output_digest:
        verdict = "identical"
    else:
        verdict = "reproduced"
    return ExperimentComparison(
        basis=basis,
        verdict=verdict,
        experiment_name=experiment_name,
        verify_script_path=verify_script_path,
        expected_verify_script_digest=expected_verify_script_digest,
        verify_script_digest=verify_script_digest,
        expected_activate_experiment_environment_script_digest=expected_activate_experiment_environment_script_digest,
        activate_experiment_environment_script_digest=activate_experiment_environment_script_digest,
        expected_verify_exit_code=expected_verify_exit_code,
        observed_verify_exit_code=observed_verify_exit_code,
        run_exit_code=run_exit_code,
        expected_output_digest=expected_output_digest,
        observed_output_digest=observed_output_digest,
        experiment_environment_digest=experiment_environment_digest,
        expected_launch_script_digest=expected_launch_script_digest,
        launch_script_digest=launch_script_digest,
    )


def _delta_records(deltas: list[PackageDelta]) -> list[PackageDeltaRecord]:
    return [
        PackageDeltaRecord(
            ecosystem=delta.ecosystem,
            name=delta.name,
            expected_version=delta.expected_version,
            observed_version=delta.observed_version,
        )
        for delta in deltas
    ]

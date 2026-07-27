"""How a reviewer's step reaches its verdict.

What settles a verdict differs per step, because the certifiable property does:

* source — SWHID identity, which *is* reproducible bit for bit;
* build — SBOM closure equivalence, because container builds are routinely not
  bit-reproducible even from identical inputs (see
  :mod:`repo2ree_core.analysis.sbom.equivalence`). A digest match is the stronger
  verdict where it happens, not the only acceptable one.
* activation — no comparison at all. There is no author artifact to reproduce
  here: the author's own activation is a precondition of a credible baseline,
  not a baseline to diff against, so "theirs passed and so did mine" would
  certify nothing beyond the second half. The reviewer's own probe is the whole
  claim, and it is recorded as an :class:`ActivationOutcome` rather than a
  comparison to keep that distinction visible in the type.
* experiments — the author's own verify script, re-run against the reviewer's
  results. Output bytes are the wrong bar: a run that stamps a timestamp or
  draws a seed produces different bytes on every honest reproduction, so
  demanding equality would report a red verdict for a result that reproduced
  perfectly. The author already declared what counts as a correct result — the
  verify script — so a pass is the verdict, and matching output digests are
  recorded as the stronger tier where they happen (see
  :func:`compare_experiment_results`).

Pure: these functions take facts and return comparison records. Nothing here
touches the filesystem.
"""

from __future__ import annotations

from repo2ree_core.analysis.sbom.cyclonedx import ObservedPackage
from repo2ree_core.analysis.sbom.equivalence import (
    PackageDelta,
    closure_verdict,
    compare_sbom_closures,
)
from repo2ree_core.evidence.review.models import (
    BuildComparison,
    BuildVerdict,
    ComparisonVerdict,
    EvidenceBasis,
    ExperimentComparison,
    ExperimentVerdict,
    PackageDeltaRecord,
    SourceComparison,
)


def compare_source_swhids(
    expected: str,
    observed: str,
    *,
    basis: EvidenceBasis = "independent",
) -> SourceComparison:
    """Compare the author's source identity with the tree the reviewer holds.

    The comparison is the same either way — a SWHID is a SWHID — but what it
    settles depends on ``basis``: an independently fetched tree agreeing with
    the recorded identity means the origin still serves the authored source,
    while an extracted snapshot agreeing means the bundle is intact.
    """
    normalized_expected = expected.strip() or None
    normalized_observed = observed.strip() or None
    if normalized_expected is None or normalized_observed is None:
        verdict: ComparisonVerdict = "inconclusive"
    elif normalized_expected == normalized_observed:
        verdict = "identical"
    else:
        verdict = "different"
    return SourceComparison(
        basis=basis,
        expected_swhid=normalized_expected,
        observed_swhid=normalized_observed,
        verdict=verdict,
    )


def compare_build_runtimes(
    *,
    expected_runtime_digest: str | None,
    observed_runtime_digest: str | None,
    expected_packages: list[ObservedPackage],
    observed_packages: list[ObservedPackage],
    expected_sbom_digest: str | None = None,
    observed_sbom_digest: str | None = None,
    sbom_tool_version: str | None = None,
    basis: EvidenceBasis = "independent",
) -> BuildComparison:
    """Certify a runtime against the author's record, digests first.

    The ladder, strongest first: equal runtime digests mean the build is bit
    reproducible (``identical``); otherwise the dependency closures decide
    (``equivalent`` / ``different``); a closure that cannot be compared at all
    — no author SBOM, or a scan that yielded nothing — is ``inconclusive``
    rather than a pass, because an absent baseline is not agreement.

    The ladder is basis-blind on purpose: a ``bundled`` runtime is scanned and
    diffed by exactly the same rules, so a shipped artifact that does *not*
    match the author's own receipt still comes back ``different``. What the
    resulting agreement is worth is carried by ``basis``, not by the verdict.
    """
    delta = compare_sbom_closures(expected_packages, observed_packages)
    if expected_runtime_digest and expected_runtime_digest == observed_runtime_digest:
        verdict: BuildVerdict = "identical"
    else:
        verdict = closure_verdict(delta)
    return BuildComparison(
        basis=basis,
        verdict=verdict,
        expected_runtime_digest=expected_runtime_digest,
        observed_runtime_digest=observed_runtime_digest,
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
    verify_script_digest: str | None,
    expected_verify_exit_code: int | None,
    observed_verify_exit_code: int | None,
    run_exit_code: int | None,
    expected_output_digest: str | None = None,
    observed_output_digest: str | None = None,
    runtime_digest: str | None = None,
) -> ExperimentComparison:
    """Settle whether one experiment reproduced, by the author's own criterion.

    The ladder, in the order it is decided:

    * No verify script declared — ``inconclusive``. All that remains is "the run
      script exited 0", which for a script whose last act is to write a results
      file says only that something ran. Reporting that as a reproduction would
      make the verdict free, and a free verdict certifies nothing.
    * The author never ran this experiment themselves — ``inconclusive``. There
      is no baseline claim to have reproduced, and an absent baseline is not
      agreement (the same rule :func:`compare_build_runtimes` applies to a
      missing SBOM).
    * Verify exited nonzero — ``different``. The author's own criterion, applied
      to the reviewer's results, rejected them. This is the step working.
    * Verify exited 0 — ``reproduced``, upgraded to ``identical`` when both
      sides recorded an output digest and the two agree.

    Note what is deliberately *not* here: a digest mismatch never downgrades a
    passing verify. Timestamps, seeds, and hostnames land in output files on
    every honest re-run, and the author already said what correctness means.
    """
    if not verify_script_path.strip():
        verdict: ExperimentVerdict = "inconclusive"
    elif expected_verify_exit_code is None:
        verdict = "inconclusive"
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
        verify_script_digest=verify_script_digest,
        expected_verify_exit_code=expected_verify_exit_code,
        observed_verify_exit_code=observed_verify_exit_code,
        run_exit_code=run_exit_code,
        expected_output_digest=expected_output_digest,
        observed_output_digest=observed_output_digest,
        runtime_digest=runtime_digest,
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

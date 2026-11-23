from __future__ import annotations

import shutil
from pathlib import Path

from repo2ree_core.analysis.sbom.cyclonedx import ObservedPackage, parse_cyclonedx
from repo2ree_core.analysis.sbom.scan import is_experiment_environment_archive, scan_experiment_environment_archive
from repo2ree_core.digests import digest_file_if_exists, digest_tree
from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_core.evidence.review.comparison import compare_build_experiment_environments
from repo2ree_core.evidence.review.records import resolve_basis, review_receipt_envelope
from repo2ree_core.evidence.review.store import write_review_build_evidence
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.execution.runners import run_workspace_script
from repo2ree_core.operations.steps.review import (
    begin_review_step,
    launch_digest,
    lay_out_review,
    require_completed_step,
    require_ree_baseline,
    require_review_record,
    review_launch,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.time_utils import OperationTimer
from repo2ree_core.workspace.attempt import discard, environment_in_workspace
from repo2ree_protocol.command import ReviewBasis, ReviewBuildExperimentEnvironmentArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import ReviewBuildExperimentEnvironmentOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import Ree
from repo2ree_ree.primitives import ReePath, WorkspacePath
from repo2ree_ree.receipt import BuildExperimentEnvironmentReceipt, GenerateSbomReceipt
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT
from repo2ree_ree.review import (
    EvidenceBasis,
    ExperimentEnvironmentComparison,
    ReviewBuildExperimentEnvironmentReceipt,
)


def handle_review_build_experiment_environment(
    args: ReviewBuildExperimentEnvironmentArgs,
    *,
    layout: ReeLayout,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    review_layout = layout.review(args.review_id)
    timer = OperationTimer.start()

    ree = require_ree_baseline(layout, log=log)
    if isinstance(ree, ActionResult):
        return ree

    record = require_review_record(review_layout, args.review_id, log)
    if isinstance(record, ActionResult):
        return record

    step = begin_review_step(
        review_layout,
        record,
        "build_experiment_environment",
        review_id=args.review_id,
        timer=timer,
        log=log,
        noun="review build",
    )
    started, stop = step.record, step.stop

    if is_canceled():
        return stop("canceled", "canceled before build")

    halted = require_completed_step(
        started,
        "acquire_source",
        stop=stop,
        message="Reproduce the source before certifying the experiment environment",
    )
    if halted is not None:
        return halted

    store = ReeDirectory(layout)
    experiment_environment_definition = ree.subject.definition.experiment_environment
    if experiment_environment_definition.artifact_path is None:
        return stop("failed", "The author baseline declares no experiment environment artifact to certify")
    experiment_environment_path = str(experiment_environment_definition.artifact_path)

    bundled_experiment_environment = store.author_artifact(experiment_environment_path)
    basis = resolve_basis(
        args.basis,
        available=_available_bases(
            layout, review_layout, has_bundled_experiment_environment=bundled_experiment_environment is not None
        ),
    )
    if basis is None:
        return stop("failed", _basis_refusal(args.basis))

    try:
        _stage_author_overlay(layout, review_layout)
    except OSError as exc:
        return stop("failed", f"could not stage the author overlay: {exc}")
    overlay_digest = digest_tree(review_layout.overlay)

    check = ree.subject.definition.check_working_environment
    try:
        workspace = lay_out_review(review_layout, started, run_id, after_build=False)
        check_launch = review_launch(started, ree, workspace)
    except ReePreconditionError as exc:
        return stop("failed", f"cannot run the author's check: {exc}")
    log("system", "info", f"review {args.review_id}: checking the working environment with the author's check")
    checked = run_workspace_script(
        workspace.resolve(),
        str(check.check_working_environment_script_path),
        log=log,
        is_canceled=is_canceled,
        launch=check_launch,
    )
    if checked.status == "canceled" or is_canceled():
        return stop("canceled", "check canceled")
    if checked.status != "succeeded":
        return stop("failed", f"the working environment does not pass the author's check (exit {checked.exit_code})")

    kept = review_layout.kept_environment(experiment_environment_path)
    kept.unlink(missing_ok=True)
    kept.parent.mkdir(parents=True, exist_ok=True)
    if basis == "bundled" and bundled_experiment_environment is not None:
        log(
            "system",
            "info",
            f"review {args.review_id}: taking the experiment environment the REE ships "
            f"at {experiment_environment_path}",
        )
        try:
            shutil.copyfile(bundled_experiment_environment, kept)
        except OSError as exc:
            return stop("failed", f"could not take the bundled experiment environment: {exc}")
        build_experiment_environment_script_digest = None
        launch, launched = None, None
    else:
        try:
            workspace = lay_out_review(review_layout, started, run_id, after_build=False)
            launch = review_launch(started, ree, workspace)
        except ReePreconditionError as exc:
            return stop("failed", f"cannot run the author's build: {exc}")
        log("system", "info", f"Build script: {RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT}")
        outcome = run_workspace_script(
            workspace.resolve(),
            RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
            log=log,
            is_canceled=is_canceled,
            launch=launch,
        )
        launched = outcome.launched
        if outcome.status == "canceled" or is_canceled():
            return stop("canceled", "build canceled")
        if outcome.status != "succeeded":
            return stop("failed", f"build script exited {outcome.exit_code}")
        build_experiment_environment_script_digest = digest_file_if_exists(
            workspace / RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT
        )
        produced = next(
            (place for place in environment_in_workspace(workspace, experiment_environment_path) if place.is_file()),
            None,
        )
        if produced is not None:
            produced.replace(kept)

    observed_artifact_digest = digest_file_if_exists(kept)
    if observed_artifact_digest is None:
        return stop("failed", f"the build produced no experiment environment artifact at {experiment_environment_path}")

    comparison = _certify(
        ree,
        layout,
        review_layout,
        experiment_environment_abs=kept,
        experiment_environment_path=experiment_environment_path,
        observed_artifact_digest=observed_artifact_digest,
        basis=basis,
        log=log,
        is_canceled=is_canceled,
    )
    if comparison is None:
        return stop("canceled", "certification canceled")

    timing = timer.finish()
    receipt = ReviewBuildExperimentEnvironmentReceipt(
        **review_receipt_envelope(run_id, timing, "succeeded"),
        build_experiment_environment_script_path=ReePath(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT)
        if basis == "independent"
        else None,
        build_experiment_environment_script_digest=build_experiment_environment_script_digest,
        artifact_path=WorkspacePath(experiment_environment_path),
        produced_artifact_digest=observed_artifact_digest,
        overlay_digest=overlay_digest,
        launch_script_digest=launch_digest(ree, launch),
        launched=launched,
    )
    write_review_build_evidence(review_layout, receipt, comparison)
    _log_verdict(comparison, log=log)
    step.settle(
        started.model_copy(
            update={
                "receipts": started.receipts.model_copy(update={"build_experiment_environment": receipt}),
                "experiment_environment_comparison": comparison,
            }
        ),
        timing,
        verdict=comparison.verdict,
        basis=comparison.basis,
        experiment_environment_digest=observed_artifact_digest,
    )

    discard(review_layout, run_id)

    outputs = ReviewBuildExperimentEnvironmentOutputs(
        review_id=args.review_id,
        receipt=receipt,
        comparison=comparison,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))


def _stage_author_overlay(ree_layout: ReeLayout, review_layout: ReviewLayout) -> None:
    if review_layout.overlay.exists():
        shutil.rmtree(review_layout.overlay)
    review_layout.root.mkdir(parents=True, exist_ok=True)
    if ree_layout.overlay.is_dir():
        shutil.copytree(ree_layout.overlay, review_layout.overlay)
    else:
        review_layout.overlay.mkdir()


def _certify(
    ree: Ree,
    ree_layout: ReeLayout,
    review_layout: ReviewLayout,
    *,
    experiment_environment_abs: Path,
    experiment_environment_path: str,
    observed_artifact_digest: str,
    basis: EvidenceBasis,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ExperimentEnvironmentComparison | None:
    author_build = ree.subject.receipts.build_experiment_environment
    author_sbom_receipt = ree.subject.receipts.generate_sbom

    expected_artifact_digest = _author_experiment_environment_digest(author_build, experiment_environment_path)
    expected_sbom_digest = (
        author_sbom_receipt.sbom_digest if isinstance(author_sbom_receipt, GenerateSbomReceipt) else None
    )

    observed_packages: list[ObservedPackage] = []
    tool_version: str | None = None
    if not is_experiment_environment_archive(experiment_environment_path):
        log(
            "system",
            "warn",
            f"cannot scan {experiment_environment_path}: SBOM comparison supports experiment environment tarballs only",
        )
    else:
        review_layout.artifacts.mkdir(parents=True, exist_ok=True)
        review_layout.sbom.unlink(missing_ok=True)
        try:
            scan = scan_experiment_environment_archive(
                experiment_environment_abs, review_layout.sbom, log=log, is_canceled=is_canceled
            )
        except OSError as exc:
            log("system", "warn", f"could not start syft ({exc}); the closure comparison is inconclusive")
        else:
            if scan.canceled:
                return None
            if scan.returncode != 0:
                log(
                    "system",
                    "warn",
                    f"syft failed (exit {scan.returncode}); the closure comparison is inconclusive",
                )
            else:
                tool_version = scan.tool_version
                observed_packages = parse_cyclonedx(review_layout.sbom.read_text(encoding="utf-8"))

    expected_packages = _author_packages(ree_layout, log=log)

    return compare_build_experiment_environments(
        expected_artifact_digest=expected_artifact_digest,
        observed_artifact_digest=observed_artifact_digest,
        expected_packages=expected_packages,
        observed_packages=observed_packages,
        expected_sbom_digest=expected_sbom_digest,
        observed_sbom_digest=digest_file_if_exists(review_layout.sbom),
        sbom_tool_version=tool_version,
        basis=basis,
    )


def _author_experiment_environment_digest(
    author_build: BuildExperimentEnvironmentReceipt | None,
    experiment_environment_path: str,
) -> str | None:
    if author_build is not None and author_build.artifact_path == experiment_environment_path:
        return author_build.produced_artifact_digest
    return None


def _author_packages(ree_layout: ReeLayout, *, log: LogSink) -> list[ObservedPackage]:
    document = ree_layout.sbom
    if not document.is_file():
        log("system", "warn", "the author baseline carries no SBOM — the closure comparison is inconclusive")
        return []
    return parse_cyclonedx(document.read_text(encoding="utf-8"))


def _has_build_recipe(ree_layout: ReeLayout, review_layout: ReviewLayout) -> bool:
    return (ree_layout.overlay / RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT).is_file() or (
        review_layout.upstream / RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT
    ).is_file()


def _available_bases(
    ree_layout: ReeLayout,
    review_layout: ReviewLayout,
    *,
    has_bundled_experiment_environment: bool,
) -> set[EvidenceBasis]:
    available: set[EvidenceBasis] = set()
    if _has_build_recipe(ree_layout, review_layout):
        available.add("independent")
    if has_bundled_experiment_environment:
        available.add("bundled")
    return available


def _basis_refusal(requested: ReviewBasis) -> str:
    if requested == "independent":
        return (
            f"The author baseline carries no {RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT} "
            "to rebuild the experiment environment with"
        )
    if requested == "bundled":
        return "This REE ships no experiment environment artifact to certify"
    return (
        f"The author baseline has neither a {RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT} "
        "nor a bundled experiment environment artifact"
    )


def _log_verdict(comparison: ExperimentEnvironmentComparison, *, log: LogSink) -> None:
    level = "info" if comparison.verdict in {"identical", "equivalent"} else "warn"
    log(
        "system",
        level,
        f"build comparison {comparison.verdict} ({comparison.basis}): {comparison.matched} packages matched, "
        f"{comparison.missing_count} missing, {comparison.extra_count} extra, "
        f"{comparison.version_mismatch_count} version mismatches "
        f"({comparison.advisory_count} advisory)",
    )
    log(
        "system",
        "info",
        f"experiment environment digest: author {comparison.expected_artifact_digest or 'none'}, "
        f"reviewer {comparison.observed_artifact_digest or 'none'}",
    )
    if comparison.basis == "bundled":
        log(
            "system",
            "warn",
            "this verdict certifies the experiment environment the REE ships against the author's own record — "
            "nothing was rebuilt, so it is an integrity check rather than an independent reproduction",
        )

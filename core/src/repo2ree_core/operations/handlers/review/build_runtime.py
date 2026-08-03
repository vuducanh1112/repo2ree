"""Rebuild and certify a runtime inside an isolated review attempt.

The reviewer-side counterpart of the author's ``build_runtime`` step. The
runtime is certified in two tiers — the produced tarball's digest, else the SBOM
dependency closure — over one of two bases: ``independent`` (rebuilt here) or
``bundled`` (the artifact the REE ships, an integrity check rather than a
reproduction).

Both bases leave the same workspace behind, because activation and the
experiments run in it and cannot tell the difference. See
``docs/engineering/review-evidence.md``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.sbom.cyclonedx import ObservedPackage, parse_cyclonedx
from repo2ree_core.analysis.sbom.scan import is_runtime_archive, scan_runtime_archive
from repo2ree_core.authoring.script_generation.materialize_workspace import build_materialize_sh
from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.domain.primitives import ReePath, WorkspacePath
from repo2ree_core.domain.ree.model import Ree
from repo2ree_core.domain.ree.receipt import (
    BuildRuntimeReceipt,
    GenerateSbomReceipt,
)
from repo2ree_core.evidence.review.comparison import compare_build_runtimes
from repo2ree_core.evidence.review.models import (
    BuildComparison,
    EvidenceBasis,
    ReviewBuildRuntimeReceipt,
    resolve_basis,
    review_receipt_envelope,
)
from repo2ree_core.evidence.review.store import write_review_build_evidence
from repo2ree_core.execution.process import (
    CancelCheck,
    format_command,
    run_streaming_process,
    run_workspace_script,
)
from repo2ree_core.operations.steps.review import (
    begin_review_step,
    require_completed_step,
    require_ree_baseline,
    require_review_record,
    workspace_runtime,
    workspace_runtime_candidates,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.command import ReviewBasis, ReviewBuildRuntimeArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class ReviewBuildRuntimeOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: ReviewBuildRuntimeReceipt
    comparison: BuildComparison


def handle_review_build_runtime(
    args: ReviewBuildRuntimeArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    ree_layout = ReeLayout.in_workbench()
    review_layout = ree_layout.review(args.review_id)
    timer = OperationTimer.start()

    ree = require_ree_baseline(ree_layout, log=log)
    if isinstance(ree, ActionResult):
        return ree

    record = require_review_record(review_layout, args.review_id, log)
    if isinstance(record, ActionResult):
        return record

    step = begin_review_step(
        review_layout,
        record,
        "build",
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
        "source",
        stop=stop,
        message="Reproduce the source before certifying the runtime",
    )
    if halted is not None:
        return halted

    store = ReeDirectory(ree_layout)
    runtime_definition = ree.subject.definition.runtime
    if runtime_definition is None:
        return stop("failed", "The author baseline declares no runtime artifact to certify")
    runtime_path = str(runtime_definition.runtime_path)

    bundled_runtime = store.author_artifact(runtime_path)
    basis = resolve_basis(
        args.basis,
        available=_available_bases(ree_layout, review_layout, has_bundled_runtime=bundled_runtime is not None),
    )
    if basis is None:
        return stop("failed", _basis_refusal(args.basis))

    # 1. Assemble the reviewer's own workspace: their upstream + the author's
    #    recipe, merged by the script the author's workbench runs. Both bases
    #    need it — it is what activation and the experiments run *in*.
    try:
        _stage_author_overlay(ree_layout, review_layout)
    except OSError as exc:
        return stop("failed", f"could not stage the author overlay: {exc}")

    write_atomic(review_layout.materialize_script, build_materialize_sh())
    command = ["sh", str(review_layout.materialize_script)]
    log("system", "info", f"review {args.review_id}: materializing into {review_layout.workspace}")
    log("system", "info", format_command(command))
    materialized = run_streaming_process(command, log=log, is_canceled=is_canceled)
    if materialized.canceled or is_canceled():
        return stop("canceled", "materialization canceled")
    if materialized.returncode != 0:
        return stop("failed", f"materialize script exited {materialized.returncode}")

    # 2. Put a runtime in that workspace: build one, or stage the shipped one.
    if basis == "bundled" and bundled_runtime is not None:
        log("system", "info", f"review {args.review_id}: staging the runtime the REE ships at {runtime_path}")
        try:
            runtime_abs = _stage_bundled_runtime(review_layout, bundled_runtime, runtime_path)
        except OSError as exc:
            return stop("failed", f"could not stage the bundled runtime: {exc}")
        build_script_digest = None
    else:
        # The author's build script, run from that workspace, unmodified.
        log("system", "info", f"Build script: {RESERVED_BUILD_SCRIPT}")
        outcome = run_workspace_script(
            review_layout.workspace.resolve(),
            RESERVED_BUILD_SCRIPT,
            log=log,
            is_canceled=is_canceled,
        )
        if outcome.status == "canceled" or is_canceled():
            return stop("canceled", "build canceled")
        if outcome.status != "succeeded":
            return stop("failed", f"build script exited {outcome.exit_code}")
        runtime_abs = workspace_runtime(review_layout, runtime_path)
        build_script_digest = digest_file_if_exists(review_layout.workspace / RESERVED_BUILD_SCRIPT)

    # 3. Certify the runtime, however it got there.
    observed_runtime_digest = digest_file_if_exists(runtime_abs)
    if observed_runtime_digest is None:
        return stop("failed", f"the build produced no runtime artifact at {runtime_path}")

    comparison = _certify(
        ree,
        ree_layout,
        review_layout,
        runtime_abs=runtime_abs,
        runtime_path=runtime_path,
        observed_runtime_digest=observed_runtime_digest,
        basis=basis,
        log=log,
        is_canceled=is_canceled,
    )
    # A cancel is not an inconclusive verdict: "nobody asked the question" must
    # not be recorded as "the evidence could not answer it".
    if comparison is None:
        return stop("canceled", "certification canceled")

    timing = timer.finish()
    # No snapshot digest and no drift verdict: both describe an author's
    # workspace drifting away from what it was materialized from, and a review
    # namespace is materialized fresh from its own acquisition every time.
    receipt = ReviewBuildRuntimeReceipt(
        **review_receipt_envelope(run_id, timing, "succeeded"),
        # A bundled certification ran no build script, so it names none: the
        # input slice of this receipt must describe what actually happened.
        build_runtime_script_path=ReePath(RESERVED_BUILD_SCRIPT) if basis == "independent" else None,
        build_runtime_script_digest=build_script_digest,
        runtime_path=WorkspacePath(runtime_path),
        produced_runtime_digest=observed_runtime_digest,
    )
    write_review_build_evidence(review_layout, receipt, comparison)
    _log_verdict(comparison, log=log)
    step.settle(
        started.model_copy(update={"build_receipt": receipt, "build_comparison": comparison}),
        timing,
        verdict=comparison.verdict,
        basis=comparison.basis,
        runtime_digest=observed_runtime_digest,
    )

    if args.prune_workspace:
        _prune_rebuilt_tree(review_layout, log=log)

    outputs = ReviewBuildRuntimeOutputs(
        review_id=args.review_id,
        receipt=receipt,
        comparison=comparison,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))


def _stage_author_overlay(ree_layout: ReeLayout, review_layout: ReviewLayout) -> None:
    """Copy the author's recipe files into the attempt, replacing any prior copy.

    A copy rather than a reference: the merge writes into the attempt's own
    workspace and a build script may write beside itself, neither of which may
    reach author evidence. Re-copying means an overlay edited between attempts
    is picked up.
    """
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
    runtime_abs: Path,
    runtime_path: str,
    observed_runtime_digest: str,
    basis: EvidenceBasis,
    log: LogSink,
    is_canceled: CancelCheck,
) -> BuildComparison | None:
    """Scan the runtime in hand and compare it with the author's recorded build.

    A scan that cannot run — unsupported artifact shape, missing scanner, absent
    author SBOM — yields an empty closure on one side, which the comparison
    reports as ``inconclusive``.

    Returns ``None`` when the scan was *canceled*, which is deliberately not one
    of those cases: the caller halts the step instead of settling a verdict.
    """
    author_build = ree.subject.receipts.build
    author_sbom_receipt = ree.subject.receipts.sbom

    expected_runtime_digest = _author_runtime_digest(author_build, runtime_path)
    expected_sbom_digest = (
        author_sbom_receipt.sbom_digest if isinstance(author_sbom_receipt, GenerateSbomReceipt) else None
    )

    observed_packages: list[ObservedPackage] = []
    tool_version: str | None = None
    if not is_runtime_archive(runtime_path):
        log("system", "warn", f"cannot scan {runtime_path}: SBOM comparison supports runtime tarballs only")
    else:
        review_layout.sbom.unlink(missing_ok=True)
        try:
            scan = scan_runtime_archive(runtime_abs, review_layout.sbom, log=log, is_canceled=is_canceled)
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

    return compare_build_runtimes(
        expected_runtime_digest=expected_runtime_digest,
        observed_runtime_digest=observed_runtime_digest,
        expected_packages=expected_packages,
        observed_packages=observed_packages,
        expected_sbom_digest=expected_sbom_digest,
        observed_sbom_digest=digest_file_if_exists(review_layout.sbom),
        sbom_tool_version=tool_version,
        basis=basis,
    )


def _author_runtime_digest(
    author_build: BuildRuntimeReceipt | None,
    runtime_path: str,
) -> str | None:
    """The digest the author recorded for the runtime this REE declares.

    Current build receipts always bind the declared runtime path to the digest
    they produced. A missing receipt or a changed path leaves no author build
    baseline to compare against.
    """
    if author_build is not None and author_build.runtime_path == runtime_path:
        return author_build.produced_runtime_digest
    return None


def _author_packages(ree_layout: ReeLayout, *, log: LogSink) -> list[ObservedPackage]:
    """The closure the author published, read from the REE's own SBOM slot.

    Read straight off ``artifacts/`` rather than resolved from a declared path:
    the author's scan writes there and a loaded bundle restores there, so both
    kinds of baseline are read identically — and a baseline that never ran the
    step simply has no file, which is inconclusive rather than wrong.
    """
    document = ree_layout.sbom
    if not document.is_file():
        log("system", "warn", "the author baseline carries no SBOM — the closure comparison is inconclusive")
        return []
    return parse_cyclonedx(document.read_text(encoding="utf-8"))


def _stage_bundled_runtime(review_layout: ReviewLayout, shipped: Path, runtime_path: str) -> Path:
    """Copy the shipped runtime into the workspace, where a rebuild would leave it.

    The author's activation and experiment scripts reach for it at the path
    their own build wrote — the last candidate when the declared path has been
    remapped into ``artifacts/``.

    Copied rather than linked: the workspace is the reviewer's to run scripts in,
    and a hard link would let one of them write through to author evidence.
    """
    target = workspace_runtime_candidates(review_layout, runtime_path)[-1]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(shipped, target)
    return target


def _has_build_recipe(ree_layout: ReeLayout, review_layout: ReviewLayout) -> bool:
    """Whether a build script exists to run over the reviewer's own source.

    Checked in both halves the materialized workspace is merged from: the
    author's overlay (where the reserved script normally lives) and the source
    tree this attempt acquired for itself.
    """
    return (ree_layout.overlay / RESERVED_BUILD_SCRIPT).is_file() or (
        review_layout.upstream / RESERVED_BUILD_SCRIPT
    ).is_file()


def _available_bases(
    ree_layout: ReeLayout,
    review_layout: ReviewLayout,
    *,
    has_bundled_runtime: bool,
) -> set[EvidenceBasis]:
    """Which bases this baseline can actually offer a runtime certification.

    A build recipe makes ``independent`` possible; the shipped artifact is the
    fallback ``auto`` reaches for when there is no script to run.
    """
    available: set[EvidenceBasis] = set()
    if _has_build_recipe(ree_layout, review_layout):
        available.add("independent")
    if has_bundled_runtime:
        available.add("bundled")
    return available


def _basis_refusal(requested: ReviewBasis) -> str:
    if requested == "independent":
        return f"The author baseline carries no {RESERVED_BUILD_SCRIPT} to rebuild the runtime with"
    if requested == "bundled":
        return "This REE ships no runtime artifact to certify"
    # auto only refuses when it had nothing at all to choose between.
    return f"The author baseline has neither a {RESERVED_BUILD_SCRIPT} nor a bundled runtime artifact"


def _log_verdict(comparison: BuildComparison, *, log: LogSink) -> None:
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
        f"runtime digest: author {comparison.expected_runtime_digest or 'none'}, "
        f"reviewer {comparison.observed_runtime_digest or 'none'}",
    )
    if comparison.basis == "bundled":
        log(
            "system",
            "warn",
            "this verdict certifies the runtime the REE ships against the author's own record — "
            "nothing was rebuilt, so it is an integrity check rather than an independent reproduction",
        )


def _prune_rebuilt_tree(review_layout: ReviewLayout, *, log: LogSink) -> None:
    """Drop the reconstructible bulk, keeping every artefact the verdict rests on.

    Never fatal: the verdict is already recorded, and failing a completed review
    over reclaimed disk space would be the wrong trade.
    """
    for directory in (review_layout.workspace, review_layout.overlay):
        try:
            if directory.is_dir():
                shutil.rmtree(directory)
        except OSError as exc:
            log("system", "warn", f"could not prune {directory.name}/: {exc}")

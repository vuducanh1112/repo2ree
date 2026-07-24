"""Rebuild and certify a runtime inside an isolated review attempt.

The reviewer-side counterpart of the author's ``build_runtime`` step, and the
first step where reproduction stops being an identity check. The source step can
demand a bit-exact SWHID; a container build cannot be held to that standard —
image builds bake in timestamps, layer ordering, and base-image tags that move
under a pinned name, so identical inputs routinely yield different bytes while
installing exactly the same software.

So the runtime is certified in two tiers (see
:func:`repo2ree_core.reviews.compare_build_runtimes`): the produced tarball's
digest, which settles ``identical`` on the rare bit-reproducible build, and
otherwise the SBOM dependency closure scanned off the runtime the reviewer just
built and diffed against the author's recorded SBOM.

Isolation works the same way it does for source: the attempt is a parallel REE
tree. The author's overlay is *copied* into it and merged with the attempt's own
independently acquired upstream by the shared materialize script, so nothing
here can write to author evidence — and the workspace the build runs in is the
reviewer's, assembled from the source they fetched themselves.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.receipts import (
    BuildRuntimeReceipt,
    GenerateSbomReceipt,
    load_author_receipts,
    receipt_run_id,
)
from repo2ree_core.ree_scripts.materialize_workspace import build_materialize_sh
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.reviews import (
    BuildComparison,
    ReviewStatus,
    compare_build_runtimes,
    read_review_record,
    step_state,
    with_step,
    write_review_build_evidence,
    write_review_record,
)
from repo2ree_core.run_script import (
    CancelCheck,
    format_command,
    run_streaming_process,
    run_workspace_script,
)
from repo2ree_core.sbom.cyclonedx import ObservedPackage, parse_cyclonedx
from repo2ree_core.sbom.scan import is_runtime_archive, scan_runtime_archive
from repo2ree_core.storage.layout import ReeLayout, ReviewLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.command import ReviewBuildRuntimeArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class ReviewBuildRuntimeOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: BuildRuntimeReceipt
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

    record = read_review_record(review_layout)
    if record is None:
        message = f"No review attempt named {args.review_id}"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)

    started = with_step(record, "build", status="running", at=timer.started_at)
    write_review_record(review_layout, started)

    def stop(status: ReviewStatus, message: str) -> ActionResult:
        timing = timer.finish()
        write_review_record(
            review_layout,
            with_step(started, "build", status=status, at=timing.finished_at, failure=message),
        )
        log("system", "warn" if status == "canceled" else "error", f"review build {status}: {message}")
        if status == "canceled":
            return ActionResult(status="canceled", outputs={"review_id": args.review_id})
        return ActionResult.failed("precondition", message)

    if is_canceled():
        return stop("canceled", "canceled before build")

    source = step_state(started, "source")
    if source is None or source.status != "completed":
        return stop("failed", "Reproduce the source before rebuilding the runtime")

    intent = ReeStore(ree_layout).read_intent()
    runtime_path = (intent.runtime or "").strip()
    if not runtime_path:
        return stop("failed", "The author baseline declares no runtime artifact to rebuild")

    # 1. Assemble the reviewer's own workspace: their upstream + the author's
    #    recipe, merged by the very script the author's workbench runs.
    try:
        _stage_author_overlay(ree_layout, review_layout)
    except Exception as exc:
        return stop("failed", f"could not stage the author overlay: {exc}")

    review_layout.materialize_script.write_bytes(build_materialize_sh())
    command = ["sh", str(review_layout.materialize_script)]
    log("system", "info", f"review {args.review_id}: materializing into {review_layout.workspace}")
    log("system", "info", format_command(command))
    materialized = run_streaming_process(command, log=log, is_canceled=is_canceled)
    if materialized.canceled or is_canceled():
        return stop("canceled", "materialization canceled")
    if materialized.returncode != 0:
        return stop("failed", f"materialize script exited {materialized.returncode}")

    # 2. Run the author's build script from that workspace, unmodified.
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

    # 3. Certify what came out.
    runtime_abs = review_layout.workspace / runtime_path
    observed_runtime_digest = digest_file_if_exists(runtime_abs)
    if observed_runtime_digest is None:
        return stop("failed", f"the build produced no runtime artifact at {runtime_path}")

    comparison = _certify(
        ree_layout,
        review_layout,
        runtime_abs=runtime_abs,
        runtime_path=runtime_path,
        observed_runtime_digest=observed_runtime_digest,
        author_sbom_path=intent.sbom,
        log=log,
    )

    timing = timer.finish()
    # No snapshot digest and no drift verdict: both describe an author's
    # workspace drifting away from what it was materialized from, and a review
    # namespace is materialized fresh from its own acquisition every time.
    receipt = BuildRuntimeReceipt(
        run_id=receipt_run_id(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
        status="succeeded",
        build_script_path=RESERVED_BUILD_SCRIPT,
        build_script_digest=digest_file_if_exists(review_layout.workspace / RESERVED_BUILD_SCRIPT),
        runtime_path=runtime_path,
        produced_runtime_digest=observed_runtime_digest,
    )
    write_review_build_evidence(review_layout, receipt, comparison)
    write_review_record(
        review_layout,
        with_step(
            started.model_copy(update={"build_receipt": receipt, "build_comparison": comparison}),
            "build",
            status="completed",
            at=timing.finished_at,
        ),
    )
    _log_verdict(comparison, log=log)
    log(
        "system",
        "info",
        f"review build succeeded in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
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
    reach author evidence. Re-running the step re-copies, so an overlay edited
    between attempts is picked up.
    """
    if review_layout.overlay.exists():
        shutil.rmtree(review_layout.overlay)
    review_layout.root.mkdir(parents=True, exist_ok=True)
    if ree_layout.overlay.is_dir():
        shutil.copytree(ree_layout.overlay, review_layout.overlay)
    else:
        review_layout.overlay.mkdir()


def _certify(
    ree_layout: ReeLayout,
    review_layout: ReviewLayout,
    *,
    runtime_abs: Path,
    runtime_path: str,
    observed_runtime_digest: str,
    author_sbom_path: str | None,
    log: LogSink,
) -> BuildComparison:
    """Scan the rebuilt runtime and compare it with the author's recorded build.

    A scan that cannot run — an unsupported artifact shape, a missing scanner,
    an absent author SBOM — yields an empty closure on one side, which the
    comparison reports as ``inconclusive``. That is the honest answer: it is a
    statement about the evidence, not about the build.
    """
    author = load_author_receipts(ree_layout)
    author_build = author.get("build_runtime")
    author_sbom_receipt = author.get("generate_sbom")

    expected_runtime_digest = (
        author_build.produced_runtime_digest if isinstance(author_build, BuildRuntimeReceipt) else None
    )
    expected_sbom_digest = (
        author_sbom_receipt.sbom_digest if isinstance(author_sbom_receipt, GenerateSbomReceipt) else None
    )

    observed_packages: list[ObservedPackage] = []
    tool_version: str | None = None
    if not is_runtime_archive(runtime_path):
        log("system", "warn", f"cannot scan {runtime_path}: SBOM comparison supports runtime tarballs only")
    else:
        scan = scan_runtime_archive(runtime_abs, review_layout.sbom, log=log)
        if scan.returncode != 0:
            log("system", "warn", f"syft failed (exit {scan.returncode}); the closure comparison is inconclusive")
        else:
            tool_version = scan.tool_version
            observed_packages = parse_cyclonedx(review_layout.sbom.read_text(encoding="utf-8"))

    expected_packages = _author_packages(ree_layout, author_sbom_path, log=log)

    return compare_build_runtimes(
        expected_runtime_digest=expected_runtime_digest,
        observed_runtime_digest=observed_runtime_digest,
        expected_packages=expected_packages,
        observed_packages=observed_packages,
        expected_sbom_digest=expected_sbom_digest,
        observed_sbom_digest=digest_file_if_exists(review_layout.sbom),
        sbom_tool_version=tool_version,
    )


def _author_packages(ree_layout: ReeLayout, sbom_path: str | None, *, log: LogSink) -> list[ObservedPackage]:
    """The closure the author published, read from the SBOM their intent names."""
    if not sbom_path:
        log("system", "warn", "the author baseline carries no SBOM — the closure comparison is inconclusive")
        return []
    document = ree_layout.workspace / sbom_path
    if not document.is_file():
        log("system", "warn", f"author SBOM not found at {sbom_path} — the closure comparison is inconclusive")
        return []
    return parse_cyclonedx(document.read_text(encoding="utf-8"))


def _log_verdict(comparison: BuildComparison, *, log: LogSink) -> None:
    level = "info" if comparison.verdict in {"identical", "equivalent"} else "warn"
    log(
        "system",
        level,
        f"build comparison {comparison.verdict}: {comparison.matched} packages matched, "
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


def _prune_rebuilt_tree(review_layout: ReviewLayout, *, log: LogSink) -> None:
    """Drop the reconstructible bulk, keeping every artefact the verdict rests on.

    Never fatal: the verdict is already recorded, and failing a completed review
    over reclaimed disk space would be the wrong trade.
    """
    for directory in (review_layout.workspace, review_layout.overlay):
        try:
            if directory.is_dir():
                shutil.rmtree(directory)
        except Exception as exc:
            log("system", "warn", f"could not prune {directory.name}/: {exc}")

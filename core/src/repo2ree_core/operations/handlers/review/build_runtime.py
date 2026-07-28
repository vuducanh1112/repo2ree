"""Rebuild and certify a runtime inside an isolated review attempt.

The reviewer-side counterpart of the author's ``build_runtime`` step, and the
first step where reproduction stops being an identity check. The source step can
demand a bit-exact SWHID; a container build cannot be held to that standard —
image builds bake in timestamps, layer ordering, and base-image tags that move
under a pinned name, so identical inputs routinely yield different bytes while
installing exactly the same software.

So the runtime is certified in two tiers (see
:func:`repo2ree_core.evidence.review.comparison.compare_build_runtimes`): the produced tarball's
digest, which settles ``identical`` on the rare bit-reproducible build, and
otherwise the SBOM dependency closure scanned off the runtime the reviewer just
built and diffed against the author's recorded SBOM.

Isolation works the same way it does for source: the attempt is a parallel REE
tree. The author's overlay is *copied* into it and merged with the attempt's own
independently acquired upstream by the shared materialize script, so nothing
here can write to author evidence — and the workspace the build runs in is the
reviewer's, assembled from the source they fetched themselves.

An REE that ships its runtime offers a second basis: certify the artifact it
already carries instead of building one. That reproduces nothing — the same
scan and the same closure diff run, but against the author's own bytes, so
agreement is expected and only *disagreement* is news (a shipped runtime that
contradicts the author's receipt). It exists because the alternative for a
baseline whose build cannot run here — no Docker, wrong architecture, no
network — is no verdict at all, and it is marked ``bundled`` on the comparison
so it can never be read as a reproduction.

What both bases share is the workspace they leave behind: source materialized
from the attempt's own acquisition, with a runtime beside it at the path the
recipe expects. Only how the runtime got there differs — built here, or copied
in from the bundle — because activation and the experiments run *in* that
workspace and cannot tell the difference, nor should they have to.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repo2ree_core.analysis.sbom.cyclonedx import ObservedPackage, parse_cyclonedx
from repo2ree_core.analysis.sbom.scan import is_runtime_archive, scan_runtime_archive
from repo2ree_core.authoring.script_generation.materialize_workspace import build_materialize_sh
from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.evidence.receipts.models import (
    BuildRuntimeReceipt,
    GenerateSbomReceipt,
    RunReceipt,
    receipt_envelope,
)
from repo2ree_core.evidence.receipts.store import load_author_receipts
from repo2ree_core.evidence.review.comparison import compare_build_runtimes
from repo2ree_core.evidence.review.models import BuildComparison, EvidenceBasis, resolve_basis
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
    require_ree_intent,
    require_review_record,
    workspace_runtime,
    workspace_runtime_candidates,
)
from repo2ree_core.ree.files import write_atomic
from repo2ree_core.ree.layout import ReeLayout, ReviewLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.command import ReviewBasis, ReviewBuildRuntimeArgs
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

    # Read before the step is marked running: a baseline nobody can read is a
    # precondition nobody can meet, so there is nothing yet to settle a halt on.
    intent = require_ree_intent(ree_layout, log=log)
    if isinstance(intent, ActionResult):
        return intent

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

    store = ReeStore(ree_layout)
    runtime_path = (intent.runtime or "").strip()
    if not runtime_path:
        return stop("failed", "The author baseline declares no runtime artifact to certify")

    bundled_runtime = store.author_artifact(runtime_path)
    basis = resolve_basis(
        args.basis,
        available=_available_bases(ree_layout, review_layout, has_bundled_runtime=bundled_runtime is not None),
    )
    if basis is None:
        return stop("failed", _basis_refusal(args.basis))

    # 1. Assemble the reviewer's own workspace: their upstream + the author's
    #    recipe, merged by the very script the author's workbench runs. Both
    #    bases need this — the workspace is not scaffolding for the build, it is
    #    what activation and the experiments run *in*, and they need the source
    #    beside the runtime whether or not this attempt built one.
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
        ree_layout,
        review_layout,
        runtime_abs=runtime_abs,
        runtime_path=runtime_path,
        observed_runtime_digest=observed_runtime_digest,
        basis=basis,
        log=log,
        is_canceled=is_canceled,
    )
    # A cancel is not an inconclusive verdict. Both leave the closure unknown,
    # but "nobody asked the question" must not be recorded as "the evidence
    # could not answer it" — the second reads as a finding about the build.
    if comparison is None:
        return stop("canceled", "certification canceled")

    timing = timer.finish()
    # No snapshot digest and no drift verdict: both describe an author's
    # workspace drifting away from what it was materialized from, and a review
    # namespace is materialized fresh from its own acquisition every time.
    receipt = BuildRuntimeReceipt(
        **receipt_envelope(run_id, timing, "succeeded"),
        # A bundled certification ran no build script, so it names none: the
        # input slice of this receipt must describe what actually happened.
        build_script_path=RESERVED_BUILD_SCRIPT if basis == "independent" else "",
        build_script_digest=build_script_digest,
        runtime_path=runtime_path,
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
    basis: EvidenceBasis,
    log: LogSink,
    is_canceled: CancelCheck,
) -> BuildComparison | None:
    """Scan the runtime in hand and compare it with the author's recorded build.

    A scan that cannot run — an unsupported artifact shape, a missing scanner,
    an absent author SBOM — yields an empty closure on one side, which the
    comparison reports as ``inconclusive``. That is the honest answer: it is a
    statement about the evidence, not about the build.

    Returns ``None`` when the scan was canceled, which is deliberately *not* one
    of those cases: an abandoned scan says nothing about the runtime, so the
    caller halts the step instead of settling a verdict over it.
    """
    author = load_author_receipts(ree_layout)
    author_build = author.get("build_runtime")
    author_sbom_receipt = author.get("generate_sbom")

    expected_runtime_digest = _author_runtime_digest(author_build, author_sbom_receipt, runtime_path, log=log)
    expected_sbom_digest = (
        author_sbom_receipt.sbom_digest if isinstance(author_sbom_receipt, GenerateSbomReceipt) else None
    )

    observed_packages: list[ObservedPackage] = []
    tool_version: str | None = None
    if not is_runtime_archive(runtime_path):
        log("system", "warn", f"cannot scan {runtime_path}: SBOM comparison supports runtime tarballs only")
    else:
        scan = scan_runtime_archive(runtime_abs, review_layout.sbom, log=log, is_canceled=is_canceled)
        if scan.canceled:
            return None
        if scan.returncode != 0:
            log("system", "warn", f"syft failed (exit {scan.returncode}); the closure comparison is inconclusive")
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
    author_build: RunReceipt | None,
    author_sbom_receipt: RunReceipt | None,
    runtime_path: str,
    *,
    log: LogSink,
) -> str | None:
    """The digest the author recorded for the runtime this REE declares.

    The build receipt is the natural home for it, but often does not have it:
    the runtime artifact is *declared after the build*, because the picker
    chooses among the files the build just produced. A build that ran before
    that choice legitimately does not know which of its outputs became the
    runtime, and its receipt is evidence of what happened — not to be rewritten
    once the author decides.

    The SBOM step runs after that choice and records ``declared_runtime_digest``
    for the file it scanned, so it answers the same question. It is only
    accepted when it scanned the artifact the REE still declares; an author who
    re-pointed ``runtime`` since would otherwise have the wrong file's digest
    compared. Without this the digest tier is dead for every REE authored in the
    natural order, and no build review could ever reach ``identical``.
    """
    if isinstance(author_build, BuildRuntimeReceipt) and author_build.produced_runtime_digest:
        return author_build.produced_runtime_digest
    if not isinstance(author_sbom_receipt, GenerateSbomReceipt):
        return None
    if author_sbom_receipt.runtime_path != runtime_path or not author_sbom_receipt.declared_runtime_digest:
        return None
    log(
        "system",
        "info",
        "the author's build receipt records no runtime digest (the artifact was declared after the build); "
        "comparing against the digest their SBOM scan recorded for the same file",
    )
    return author_sbom_receipt.declared_runtime_digest


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

    Both bases have to leave the same workspace behind, because the steps after
    this one do not care how the runtime got there — the author's activation and
    experiment scripts reach for it at the path their own build wrote, which is
    the last candidate when the declared path has been remapped into
    ``artifacts/``.

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

    A recipe is what makes the independent path possible, because a rebuild is
    the only thing here that reproduces anything; the shipped artifact is the
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

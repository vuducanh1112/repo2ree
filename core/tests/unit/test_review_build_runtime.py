"""Reviewer-side runtime reproduction: isolation, preconditions, and verdicts.

The scanner is stubbed throughout — these tests are about what the handler
compares and where it writes, not about syft.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from repo2ree_core.analysis.sbom.scan import ScanOutcome
from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.evidence.receipts.models import BuildRuntimeReceipt, GenerateSbomReceipt
from repo2ree_core.evidence.receipts.store import record_receipt
from repo2ree_core.evidence.review.models import new_review_record, step_state, with_step
from repo2ree_core.evidence.review.store import load_reviews, write_review_record
from repo2ree_core.operations.handlers.review import build_runtime as handler
from repo2ree_core.ree.layout import SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.ree.workspace.model import WorkspaceMetadata
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_protocol.command import ReviewBuildRuntimeArgs

RUNTIME_PATH = "runtime.tar"

# A build script that "produces" a runtime tarball with deterministic contents,
# so a rebuild is bit-identical unless a test says otherwise.
_BUILD_SCRIPT = """#!/bin/sh
set -eu
printf 'runtime bytes\\n' > runtime.tar
"""


def _sbom(packages: list[tuple[str, str, str]]) -> str:
    return json.dumps(
        {
            "components": [
                {"name": name, "version": version, "purl": f"pkg:{kind}/{name}@{version}"}
                for kind, name, version in packages
            ]
        }
    )


AUTHOR_PACKAGES = [("pypi", "numpy", "1.26.4"), ("pypi", "requests", "2.31.0")]


def _author_ree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    build_script: str = _BUILD_SCRIPT,
    author_runtime_digest: str | None = None,
    author_sbom: str | None = None,
) -> ReeLayout:
    """An author baseline with a build script, a runtime receipt, and an SBOM."""
    layout = ReeLayout(root=tmp_path / "ree")
    store = ReeStore(layout)
    store.ensure_dirs()
    store.write_metadata(
        WorkspaceMetadata(
            ree_id="ree-review",
            name="review",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            ree_intent=ReeIntent(
                name="review",
                runtime=RUNTIME_PATH,
                sbom=SBOM_ARTIFACT_PATH if author_sbom is not None else None,
            ),
            ree_session=ReeSession(),
        )
    )

    # The author's recipe lives in the overlay; the review copies it.
    script = layout.overlay / RESERVED_BUILD_SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(build_script, encoding="utf-8")

    if author_sbom is not None:
        layout.sbom.write_text(author_sbom, encoding="utf-8")

    record_receipt(
        layout,
        BuildRuntimeReceipt(
            run_id="author-build",
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_ms=1000,
            recorded_at="2026-01-01T00:00:01Z",
            status="succeeded",
            build_script_path=RESERVED_BUILD_SCRIPT,
            runtime_path=RUNTIME_PATH,
            produced_runtime_digest=author_runtime_digest,
        ),
        log=lambda *_: None,
    )
    record_receipt(
        layout,
        GenerateSbomReceipt(
            run_id="author-sbom",
            started_at="2026-01-01T00:00:02Z",
            finished_at="2026-01-01T00:00:03Z",
            duration_ms=1000,
            recorded_at="2026-01-01T00:00:03Z",
            status="succeeded",
            runtime_path=RUNTIME_PATH,
            sbom_path=SBOM_ARTIFACT_PATH,
            sbom_digest="sha256:" + "a" * 64,
        ),
        log=lambda *_: None,
    )

    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    return layout


def _reviewed_source(layout: ReeLayout, review_id: str = "review-one", *, status: str = "completed") -> None:
    """An attempt whose source step has already run, with its upstream in place."""
    review = layout.review(review_id)
    review.upstream.mkdir(parents=True, exist_ok=True)
    (review.upstream / "main.py").write_text("print('hi')\n", encoding="utf-8")
    write_review_record(
        review,
        with_step(
            new_review_record(review_id, at="2026-07-24T10:00:00Z"),
            "source",
            status=status,  # type: ignore[arg-type]
            at="2026-07-24T10:00:01Z",
        ),
    )


def _stub_scan(monkeypatch: pytest.MonkeyPatch, packages: list[tuple[str, str, str]] | None) -> None:
    """Stand in for syft: write the closure the reviewer's runtime "contains"."""

    def scan(_runtime: Path, output_path: Path, **_kwargs: Any) -> ScanOutcome:
        if packages is None:
            return ScanOutcome(returncode=1)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_sbom(packages), encoding="utf-8")
        return ScanOutcome(returncode=0, tool_version="1.2.3")

    monkeypatch.setattr(handler, "scan_runtime_archive", scan)


def _build(review_id: str = "review-one", *, prune_workspace: bool = False, basis: str = "auto") -> Any:
    return handler.handle_review_build_runtime(
        ReviewBuildRuntimeArgs(review_id=review_id, prune_workspace=prune_workspace, basis=basis),  # type: ignore[arg-type]
        run_id="review-build-run",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )


def _ship_runtime(
    layout: ReeLayout,
    *,
    at: str = f"artifacts/{RUNTIME_PATH}",
    contents: str = "shipped bytes\n",
) -> str:
    """Give the baseline a runtime artifact the way a loaded bundle carries one.

    Bundling lifts the runtime into ``artifacts/`` and rewrites the declared
    path to match, so the intent points outside ``workspace/`` — which is
    exactly the shape a bundled-basis review has to cope with.
    """
    store = ReeStore(layout)
    artifact = layout.ree_file(at)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(contents, encoding="utf-8")
    metadata = store.read_metadata()
    store.write_metadata(
        metadata.model_copy(update={"ree_intent": metadata.ree_intent.model_copy(update={"runtime": at})})
    )
    return at


def test_matching_closure_certifies_the_rebuild_as_equivalent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(
        tmp_path,
        monkeypatch,
        author_runtime_digest="sha256:" + "f" * 64,  # a digest the rebuild cannot match
        author_sbom=_sbom(AUTHOR_PACKAGES),
    )
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    result = _build()

    assert result.status == "succeeded"
    comparison = result.outputs["comparison"]
    assert comparison["verdict"] == "equivalent"
    assert comparison["matched"] == 2
    assert comparison["sbom_tool_version"] == "1.2.3"


def test_a_bit_identical_rebuild_is_the_stronger_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    # Learn the digest this build produces, then re-run against it as the author's.
    first = _build()
    produced = first.outputs["comparison"]["observed_runtime_digest"]

    layout = _author_ree(
        tmp_path / "second",
        monkeypatch,
        author_runtime_digest=produced,
        author_sbom=_sbom(AUTHOR_PACKAGES),
    )
    _reviewed_source(layout)

    assert _build().outputs["comparison"]["verdict"] == "identical"


def test_drifted_dependencies_are_reported_as_different(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(
        tmp_path,
        monkeypatch,
        author_runtime_digest="sha256:" + "f" * 64,
        author_sbom=_sbom(AUTHOR_PACKAGES),
    )
    _reviewed_source(layout)
    _stub_scan(monkeypatch, [("pypi", "numpy", "2.0.0"), ("pypi", "requests", "2.31.0")])

    comparison = _build().outputs["comparison"]

    assert comparison["verdict"] == "different"
    assert comparison["version_mismatch_count"] == 1
    assert comparison["version_mismatches"][0]["name"] == "numpy"


def test_an_author_baseline_without_an_sbom_is_inconclusive_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _author_ree(tmp_path, monkeypatch, author_runtime_digest="sha256:" + "f" * 64)
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    assert _build().outputs["comparison"]["verdict"] == "inconclusive"


def test_a_failed_scan_is_inconclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(
        tmp_path,
        monkeypatch,
        author_runtime_digest="sha256:" + "f" * 64,
        author_sbom=_sbom(AUTHOR_PACKAGES),
    )
    _reviewed_source(layout)
    _stub_scan(monkeypatch, None)

    assert _build().outputs["comparison"]["verdict"] == "inconclusive"


def test_a_canceled_scan_is_not_recorded_as_an_inconclusive_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "Nobody asked" and "the evidence could not answer" must stay distinct.

    Both leave the closure unknown, but only the second is a finding about the
    build — recording a cancel as ``inconclusive`` would complete the step with
    a verdict nothing established.
    """
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _reviewed_source(layout)

    def canceled_scan(_runtime: Path, _output: Path, **_kwargs: Any) -> ScanOutcome:
        return ScanOutcome(returncode=-15, canceled=True)

    monkeypatch.setattr(handler, "scan_runtime_archive", canceled_scan)

    result = _build()

    assert result.status == "canceled"
    record = load_reviews(layout).reviews[0]
    build = step_state(record, "build")
    assert build is not None and build.status == "canceled"
    assert record.build_comparison is None


def test_the_rebuild_is_isolated_from_author_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    _build()

    review = layout.review("review-one")
    # The runtime was produced in the review's own workspace...
    assert (review.workspace / RUNTIME_PATH).is_file()
    assert (review.workspace / "main.py").is_file()
    # ...and the author's workspace, artifacts, and receipts are untouched.
    assert not (layout.workspace / RUNTIME_PATH).exists()
    assert list(layout.artifacts.iterdir()) == [layout.sbom]
    # The reviewer's own scan wrote to their attempt, never over the author's.
    assert layout.sbom.read_text(encoding="utf-8") == _sbom(AUTHOR_PACKAGES)
    author_build = (layout.author_receipts / "build_runtime.json").read_text(encoding="utf-8")
    assert "review-build-run" not in author_build
    # Reviewer evidence lands in the attempt.
    assert review.operation_receipt("build_runtime").is_file()
    assert review.comparison("build").is_file()
    assert review.sbom.is_file()


def test_pruning_reclaims_the_rebuilt_tree_but_keeps_the_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    assert _build(prune_workspace=True).status == "succeeded"

    review = layout.review("review-one")
    assert not review.workspace.exists()
    assert not review.overlay.exists()
    assert review.sbom.is_file()
    assert review.comparison("build").is_file()
    assert review.upstream.is_dir()


def test_building_before_the_source_step_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _reviewed_source(layout, status="failed")

    result = _build()

    assert result.status == "failed"
    record = load_reviews(layout).reviews[0]
    build = step_state(record, "build")
    assert build is not None
    assert build.status == "failed"
    assert record.status == "failed"


def test_an_unknown_attempt_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))

    result = _build("review-nonexistent")

    assert result.status == "failed"
    assert result.failure is not None
    assert "review-nonexistent" in result.failure.message


def test_a_failing_build_script_fails_the_step_and_the_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(
        tmp_path,
        monkeypatch,
        build_script="#!/bin/sh\nexit 3\n",
        author_sbom=_sbom(AUTHOR_PACKAGES),
    )
    _reviewed_source(layout)

    result = _build()

    assert result.status == "failed"
    record = load_reviews(layout).reviews[0]
    assert record.status == "failed"
    assert record.build_comparison is None
    assert record.failure is not None and "exited 3" in record.failure


# ================================================
# Bundled basis: certifying the runtime the REE ships
# ================================================


def test_a_bundled_runtime_is_certified_against_the_author_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shipped artifact matching the author's own record earns ``identical``.

    Expected, and that is the point: the verdict here says the bundle is
    internally consistent, which is only worth reading because ``basis`` says
    where it came from.
    """
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    at = _ship_runtime(layout)
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)
    # Re-record the author's build receipt against the digest of what it shipped.
    shipped = digest_file_if_exists(layout.ree_file(at))
    record_receipt(
        layout,
        BuildRuntimeReceipt(
            run_id="author-build",
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_ms=1000,
            recorded_at="2026-01-01T00:00:01Z",
            status="succeeded",
            build_script_path=RESERVED_BUILD_SCRIPT,
            runtime_path=at,
            produced_runtime_digest=shipped,
        ),
        log=lambda *_: None,
    )

    result = _build(basis="bundled")

    assert result.status == "succeeded"
    comparison = result.outputs["comparison"]
    assert comparison["basis"] == "bundled"
    assert comparison["verdict"] == "identical"
    assert comparison["observed_runtime_digest"] == shipped
    # Nothing was built, so the receipt names no build script.
    assert result.outputs["receipt"]["build_script_path"] == ""


def test_a_shipped_runtime_contradicting_the_author_sbom_is_still_different(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The weaker basis is not a weaker check — disagreement is the whole point."""
    layout = _author_ree(
        tmp_path,
        monkeypatch,
        author_runtime_digest="sha256:" + "f" * 64,
        author_sbom=_sbom(AUTHOR_PACKAGES),
    )
    _ship_runtime(layout)
    _reviewed_source(layout)
    _stub_scan(monkeypatch, [("pypi", "numpy", "2.0.0"), ("pypi", "requests", "2.31.0")])

    comparison = _build(basis="bundled").outputs["comparison"]

    assert comparison["basis"] == "bundled"
    assert comparison["verdict"] == "different"
    assert comparison["version_mismatch_count"] == 1


def test_certifying_the_bundle_never_runs_the_build_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(
        tmp_path,
        monkeypatch,
        build_script="#!/bin/sh\nexit 3\n",  # would fail the step if it ran
        author_sbom=_sbom(AUTHOR_PACKAGES),
    )
    _ship_runtime(layout)
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    result = _build(basis="bundled")

    assert result.status == "succeeded"
    # The author's shipped artifact is read, never moved or rewritten.
    assert layout.ree_file(f"artifacts/{RUNTIME_PATH}").is_file()


def test_a_bundled_certification_still_leaves_a_runnable_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Activation and the experiments run *in* the reviewer's workspace.

    They need the source materialized and a runtime beside it whatever this step
    did to get one, so a bundled certification cannot skip the merge — and the
    runtime has to land where the recipe expects it, not where the bundle
    happened to declare it.
    """
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _ship_runtime(layout, contents="the shipped runtime\n")  # declares artifacts/runtime.tar
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    assert _build(basis="bundled").status == "succeeded"

    workspace = layout.review("review-one").workspace
    # The reviewer's own source, merged with the author's recipe.
    assert (workspace / "main.py").is_file()
    assert (workspace / RESERVED_BUILD_SCRIPT).is_file()
    # The runtime sits where a rebuild would have written it — the packaging
    # remap into artifacts/ is undone, since no build script writes there.
    assert (workspace / RUNTIME_PATH).read_text(encoding="utf-8") == "the shipped runtime\n"


def test_pruning_reclaims_a_bundled_attempt_the_same_way(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both bases leave the same workspace, so both reclaim it the same way."""
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _ship_runtime(layout)
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    assert _build(basis="bundled", prune_workspace=True).status == "succeeded"

    review = layout.review("review-one")
    assert not review.workspace.exists()
    assert review.sbom.is_file()
    assert review.comparison("build").is_file()


def test_auto_prefers_a_real_rebuild_over_the_shipped_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _ship_runtime(layout, contents="not what the build produces\n")
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    result = _build(basis="auto")

    assert result.outputs["comparison"]["basis"] == "independent"
    assert (layout.review("review-one").workspace / "runtime.tar").is_file()


def test_auto_falls_back_to_the_bundle_when_there_is_no_build_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    (layout.overlay / RESERVED_BUILD_SCRIPT).unlink()
    _ship_runtime(layout)
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    assert _build(basis="auto").outputs["comparison"]["basis"] == "bundled"


def test_an_explicit_basis_is_refused_rather_than_downgraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Silently answering a weaker question than the one asked is the one
    failure this step cannot afford."""
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    (layout.overlay / RESERVED_BUILD_SCRIPT).unlink()
    _ship_runtime(layout)
    _reviewed_source(layout)

    result = _build(basis="independent")

    assert result.status == "failed"
    assert result.failure is not None and RESERVED_BUILD_SCRIPT in result.failure.message


def test_asking_for_a_bundled_runtime_the_ree_does_not_carry_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _reviewed_source(layout)

    result = _build(basis="bundled")

    assert result.status == "failed"
    assert result.failure is not None and "ships no runtime artifact" in result.failure.message


def test_the_author_closure_is_read_from_the_ree_slot_not_the_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A workspace file named sbom.json is source, never the author's evidence.

    The author's scan and a loaded bundle both fill ``artifacts/sbom.json``, so
    that is the only place the closure is read from. A repository that happens
    to carry its own ``sbom.json`` cannot stand in for a scan that never ran —
    the comparison must say inconclusive rather than certify against source.
    """
    layout = _author_ree(tmp_path, monkeypatch, author_runtime_digest="sha256:" + "f" * 64)
    layout.workspace.mkdir(parents=True, exist_ok=True)
    (layout.workspace / "sbom.json").write_text(_sbom(AUTHOR_PACKAGES), encoding="utf-8")
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    comparison = _build().outputs["comparison"]

    assert comparison["verdict"] == "inconclusive"
    assert comparison["matched"] == 0


def test_a_rebuild_finds_the_runtime_a_loaded_bundle_declares_under_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Packaging rewrote the declared path; the build script did not change.

    Without undoing that remap an independently rebuilt loaded REE would report
    "the build produced no runtime artifact" while the artifact sat right there
    in the workspace.
    """
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _ship_runtime(layout, contents="the shipped copy\n")  # declares artifacts/runtime.tar
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    result = _build(basis="independent")

    assert result.status == "succeeded"
    assert result.outputs["comparison"]["basis"] == "independent"
    # The digest is of what the build wrote, not of the copy the bundle shipped.
    rebuilt = digest_file_if_exists(layout.review("review-one").workspace / RUNTIME_PATH)
    assert result.outputs["comparison"]["observed_runtime_digest"] == rebuilt


# ================================================
# The author's recorded runtime digest
# ================================================


def _author_declared_runtime(layout: ReeLayout, digest: str | None, *, runtime_path: str = RUNTIME_PATH) -> None:
    """Re-record the author's evidence the way the authoring order produces it.

    The build ran before the runtime artifact was declared, so its receipt names
    no artifact and carries no digest; the SBOM step ran after and recorded the
    digest of the file it scanned.
    """
    record_receipt(
        layout,
        BuildRuntimeReceipt(
            run_id="author-build",
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_ms=1000,
            recorded_at="2026-01-01T00:00:01Z",
            status="succeeded",
            build_script_path=RESERVED_BUILD_SCRIPT,
            runtime_path=None,
            produced_runtime_digest=None,
        ),
        log=lambda *_: None,
    )
    record_receipt(
        layout,
        GenerateSbomReceipt(
            run_id="author-sbom",
            started_at="2026-01-01T00:00:02Z",
            finished_at="2026-01-01T00:00:03Z",
            duration_ms=1000,
            recorded_at="2026-01-01T00:00:03Z",
            status="succeeded",
            runtime_path=runtime_path,
            declared_runtime_digest=digest,
            sbom_path=SBOM_ARTIFACT_PATH,
            sbom_digest="sha256:" + "a" * 64,
        ),
        log=lambda *_: None,
    )


def test_the_digest_the_sbom_scan_recorded_stands_in_for_the_build_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The artifact is declared *after* the build, so the build receipt names none.

    Reading only the build receipt leaves the digest tier dead for every REE
    authored in the natural order — no reproduction could ever earn ``identical``,
    however bit-exact it was.
    """
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)
    # Learn what this build produces, then record it as the author's SBOM scan did.
    produced = _build().outputs["comparison"]["observed_runtime_digest"]
    _author_declared_runtime(layout, produced)
    _reviewed_source(layout, "review-two")

    comparison = _build("review-two").outputs["comparison"]

    assert comparison["expected_runtime_digest"] == produced
    assert comparison["verdict"] == "identical"


def test_a_digest_scanned_from_a_different_artifact_is_not_borrowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the file the REE still declares can answer for it.

    An author who re-pointed ``runtime`` after generating the SBOM would
    otherwise have an unrelated file's digest compared against the rebuild.
    """
    layout = _author_ree(tmp_path, monkeypatch, author_sbom=_sbom(AUTHOR_PACKAGES))
    _author_declared_runtime(layout, "sha256:" + "e" * 64, runtime_path="some/other.tar")
    _reviewed_source(layout)
    _stub_scan(monkeypatch, AUTHOR_PACKAGES)

    comparison = _build().outputs["comparison"]

    assert comparison["expected_runtime_digest"] is None
    # The closure still decides, so the absent digest costs no evidence.
    assert comparison["verdict"] == "equivalent"

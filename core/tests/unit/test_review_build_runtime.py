"""Reviewer-side runtime reproduction: isolation, preconditions, and verdicts.

The scanner is stubbed throughout — these tests are about what the handler
compares and where it writes, not about syft.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.envelope.handlers import review_build_runtime as handler
from repo2ree_core.receipts import BuildRuntimeReceipt, GenerateSbomReceipt, record_receipt
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.reviews import (
    load_reviews,
    new_review_record,
    step_state,
    with_step,
    write_review_record,
)
from repo2ree_core.sbom.scan import ScanOutcome
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.workspace.model import WorkspaceMetadata
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
                sbom="sbom.json" if author_sbom is not None else None,
            ),
            ree_session=ReeSession(),
        )
    )

    # The author's recipe lives in the overlay; the review copies it.
    script = layout.overlay / RESERVED_BUILD_SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(build_script, encoding="utf-8")

    if author_sbom is not None:
        layout.workspace.mkdir(parents=True, exist_ok=True)
        (layout.workspace / "sbom.json").write_text(author_sbom, encoding="utf-8")

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
            sbom_path="sbom.json",
            sbom_digest="sha256:" + "a" * 64,
        ),
        log=lambda *_: None,
    )

    monkeypatch.setattr(handler.ReeLayout, "in_workbench", classmethod(lambda cls: layout))
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


def _build(review_id: str = "review-one", *, prune_workspace: bool = False) -> Any:
    return handler.handle_review_build_runtime(
        ReviewBuildRuntimeArgs(review_id=review_id, prune_workspace=prune_workspace),
        run_id="review-build-run",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )


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
    assert not layout.artifacts.exists() or not any(layout.artifacts.iterdir())
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

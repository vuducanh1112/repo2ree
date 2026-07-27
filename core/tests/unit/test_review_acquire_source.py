"""Reviewer-side source acquisition: which tree an attempt verifies, and why.

The two bases are the subject here. The origin fetch is never exercised for
real — these tests are about what the handler stages, what it refuses, and how
it labels the verdict, not about git.
"""

from __future__ import annotations

import tarfile
from pathlib import Path
from typing import Any

import pytest

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.envelope.handlers import review_acquire_source as handler
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.workspace.model import WorkspaceMetadata
from repo2ree_protocol.command import ReviewAcquireSourceArgs

SWHID = "swh:1:dir:" + "a" * 40


def _author_ree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    origin_url: str = "https://example.invalid/project.git",
    source_type: str = "git",
    with_snapshot: bool = False,
) -> ReeLayout:
    """A baseline that may carry an origin, a snapshot, or both."""
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
                origin_url=origin_url,
                source_type=source_type,  # type: ignore[arg-type]
                swhid=SWHID,
            ),
            ree_session=ReeSession(),
        )
    )
    if with_snapshot:
        source = tmp_path / "source"
        source.mkdir()
        (source / "main.py").write_text("print('bundled')\n", encoding="utf-8")
        with tarfile.open(layout.snapshot_archive, "w:gz") as archive:
            for entry in sorted(source.iterdir()):
                archive.add(entry, arcname=entry.name)

    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    return layout


def _stub_swhid(monkeypatch: pytest.MonkeyPatch, observed: str = SWHID) -> None:
    monkeypatch.setattr(handler, "directory_swhid", lambda _path: observed)


def _acquire(review_id: str = "review-one", *, basis: str = "auto") -> Any:
    return handler.handle_review_acquire_source(
        ReviewAcquireSourceArgs(review_id=review_id, basis=basis),  # type: ignore[arg-type]
        run_id="review-source-run",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )


def test_the_bundled_snapshot_is_extracted_and_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch, origin_url="", source_type="", with_snapshot=True)
    _stub_swhid(monkeypatch)

    result = _acquire()

    assert result.status == "succeeded"
    comparison = result.outputs["comparison"]
    assert comparison["basis"] == "bundled"
    assert comparison["verdict"] == "identical"
    review = layout.review("review-one")
    assert (review.upstream / "main.py").read_text(encoding="utf-8") == "print('bundled')\n"
    # The receipt names no origin: the acquisition contacted none.
    assert result.outputs["receipt"]["origin_url"] == ""


def test_an_upload_acquired_ree_is_reviewable_at_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The case the origin-only path had no answer for.

    An REE whose source was uploaded, or loaded from a bundle, has no origin to
    fetch — and refusing it meant its build, activation, and experiments could
    never be reviewed either, since every later step gates on this one.
    """
    _author_ree(tmp_path, monkeypatch, origin_url="", source_type="", with_snapshot=True)
    _stub_swhid(monkeypatch)

    assert _acquire(basis="auto").status == "succeeded"


def test_a_tampered_snapshot_is_reported_as_different(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bundled basis is a weaker claim, not a weaker check."""
    _author_ree(tmp_path, monkeypatch, origin_url="", source_type="", with_snapshot=True)
    _stub_swhid(monkeypatch, observed="swh:1:dir:" + "b" * 40)

    comparison = _acquire(basis="bundled").outputs["comparison"]

    assert comparison["verdict"] == "different"
    assert comparison["basis"] == "bundled"


def test_asking_for_a_bundled_basis_without_a_snapshot_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _author_ree(tmp_path, monkeypatch, with_snapshot=False)

    result = _acquire(basis="bundled")

    assert result.status == "failed"
    assert result.failure is not None and "no source snapshot" in result.failure.message


def test_asking_for_an_independent_basis_without_an_origin_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never quietly downgraded: a reviewer who asked to reproduce from the
    origin must not be handed an integrity check wearing the same verdict."""
    _author_ree(tmp_path, monkeypatch, origin_url="", source_type="", with_snapshot=True)

    result = _acquire(basis="independent")

    assert result.status == "failed"
    assert result.failure is not None and "independently acquirable" in result.failure.message


def test_a_baseline_with_neither_origin_nor_snapshot_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _author_ree(tmp_path, monkeypatch, origin_url="", source_type="", with_snapshot=False)

    result = _acquire()

    assert result.status == "failed"
    assert result.failure is not None and "neither" in result.failure.message


def test_auto_prefers_the_origin_when_the_baseline_has_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The strongest available evidence, without the reviewer having to ask.

    Asserted through the staged script rather than a fetch: the generated
    ``acquire_source.sh`` bakes in the origin only for an independent basis, and
    the snapshot beside it is what would otherwise win at runtime.
    """
    layout = _author_ree(tmp_path, monkeypatch, with_snapshot=True)
    fetched: list[Path] = []

    def fake_run(command: list[str], **_kwargs: Any) -> Any:
        fetched.append(Path(command[-1]))
        review = layout.review("review-one")
        review.upstream.mkdir(parents=True, exist_ok=True)
        (review.upstream / "main.py").write_text("print('fetched')\n", encoding="utf-8")

        class _Result:
            returncode = 0
            canceled = False

        return _Result()

    monkeypatch.setattr(handler, "run_streaming_process", fake_run)
    _stub_swhid(monkeypatch)

    comparison = _acquire().outputs["comparison"]

    assert comparison["basis"] == "independent"
    review = layout.review("review-one")
    # No snapshot was staged, so the script cannot silently prefer it.
    assert not review.snapshot_archive.exists()
    assert "example.invalid" in review.acquire_script.read_text(encoding="utf-8")


def test_re_running_on_a_different_basis_replaces_the_acquired_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acquire script leaves a populated upstream alone, so the step clears
    it first — otherwise a second basis would report the first one's tree."""
    layout = _author_ree(tmp_path, monkeypatch, origin_url="", source_type="", with_snapshot=True)
    _stub_swhid(monkeypatch)
    review = layout.review("review-one")
    review.upstream.mkdir(parents=True, exist_ok=True)
    (review.upstream / "stale.py").write_text("# from a previous attempt\n", encoding="utf-8")

    assert _acquire(basis="bundled").status == "succeeded"

    assert not (review.upstream / "stale.py").exists()
    assert (review.upstream / "main.py").is_file()

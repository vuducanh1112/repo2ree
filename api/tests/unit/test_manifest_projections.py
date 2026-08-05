"""Routes that read meaning out of a workbench's REE document.

The workbench hands its document back as JSON and the supervisor relays it
unparsed — deliberately, since that package may not know the domain shape. That
makes the control plane the first place the bytes mean anything, and these
tests pin that it *parses* them rather than indexing them.

The distinction is not stylistic. ``dict.get`` answers ``None`` for a path that
has stopped existing, so a projection reading the document by key degrades into
a plausible wrong answer instead of an error — which is exactly how every
downloaded bundle came to be named ``ree.zip`` while three refactors renamed the
source of that dict and nobody noticed the path into it had gone dead.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.archives import archive_download_filename
from repo2ree_core.domain.ree.model import (
    Ree,
    ReeDefinition,
    ReeSeal,
    ReeSubject,
    canonical_subject_digest,
)
from repo2ree_core.time_utils import utc_now_instant
from repo2ree_supervisor import WorkbenchHandle


def _manifest(name: str, *, sealed: bool = False) -> dict[str, Any]:
    subject = ReeSubject(definition=ReeDefinition(name=name))
    seal = ReeSeal(sealed_at=utc_now_instant(), ree_digest=canonical_subject_digest(subject)) if sealed else None
    return Ree(subject=subject, seal=seal).model_dump(mode="json", exclude_none=True)


# ================================================
# Archive filename
# ================================================


def test_archive_is_named_after_the_ree(online_ree: WorkbenchHandle, monkeypatch: pytest.MonkeyPatch) -> None:
    """The name lives at ``subject.definition.name``, not at the document root.

    A regression pin with a specific history: this read was
    ``manifest.get("name")``, and ``Ree`` has exactly one top-level key
    (``subject``). Every bundle downloaded as ``ree.zip`` — the fallback for an
    unnamed REE — so the failure looked like a design choice.
    """
    monkeypatch.setattr(workbench_manager, "get_ree_manifest", lambda handle: _manifest("My Study"))

    assert archive_download_filename(online_ree) == "My_Study.zip"


def test_an_unnamed_ree_still_downloads(online_ree: WorkbenchHandle, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fallback is for a genuinely blank name, which the domain permits."""
    monkeypatch.setattr(workbench_manager, "get_ree_manifest", lambda handle: _manifest(""))

    assert archive_download_filename(online_ree) == "ree.zip"


# ================================================
# Listing projection
# ================================================


def _staged(monkeypatch: pytest.MonkeyPatch, entries: list[tuple[str, dict[str, Any]]]) -> None:
    manifests = [
        (WorkbenchHandle(ree_id=rid, container_name=f"wb-{rid}", volume_name=f"vol-{rid}"), manifest)
        for rid, manifest in entries
    ]
    monkeypatch.setattr(workbench_manager, "list_all_manifests", lambda: manifests)
    monkeypatch.setattr(workbench_manager, "image_for", lambda handle: "bench:test")


def test_listing_projects_name_and_status_from_the_parsed_document(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _staged(monkeypatch, [("a1", _manifest("Alpha")), ("b2", _manifest("Beta", sealed=True))])

    items = client.get("/api/v1/rees").json()["items"]

    assert {item["name"]: item["status"] for item in items} == {"Alpha": "draft", "Beta": "sealed"}


def test_status_filter_reads_the_derived_status(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """``status`` is derived by core's ``ree_status``, not re-read from the seal.

    The projection used to decide this itself (``"sealed" if ree.get("seal")``),
    a second definition of what a seal means, in a package that may not know.
    """
    _staged(monkeypatch, [("a1", _manifest("Alpha")), ("b2", _manifest("Beta", sealed=True))])

    items = client.get("/api/v1/rees", params={"status": "sealed"}).json()["items"]

    assert [item["name"] for item in items] == ["Beta"]


def test_an_unparsable_document_drops_out_instead_of_failing_the_listing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One workbench this node cannot read must not empty the whole list.

    The same treatment an unreachable bench already gets: to a caller the two
    are one event — a workbench this control plane cannot report on. It matters
    because the document may come from a bench running a core this node was
    never built against (see the workbench image catalog).
    """
    _staged(monkeypatch, [("a1", _manifest("Alpha")), ("bad", {"subject": {"definition": {"nope": 1}}})])

    items = client.get("/api/v1/rees").json()["items"]

    assert [item["name"] for item in items] == ["Alpha"]

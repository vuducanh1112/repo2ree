"""Routes that read meaning out of a workbench's REE."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import command_dispatcher, ree_registry
from repo2ree_api.workbench.archives import archive_download_filename
from repo2ree_core.time_utils import utc_now_instant
from repo2ree_ree.model import Ree, ReeDefinition, ReeSeal, ReeSubject, canonical_subject_digest, ree_status
from repo2ree_supervisor import ReeRoute


def _manifest(name: str, *, sealed: bool = False) -> Ree:
    subject = ReeSubject(definition=ReeDefinition(name=name))
    seal = ReeSeal(sealed_at=utc_now_instant(), ree_digest=canonical_subject_digest(subject)) if sealed else None
    return Ree(subject=subject, seal=seal)


# ================================================
# Archive filename
# ================================================


def test_archive_is_named_after_the_ree(online_ree: ReeRoute, monkeypatch: pytest.MonkeyPatch) -> None:
    """The name lives at ``subject.definition.name``, not at the document root.

    A regression pin with a specific history: this read was
    ``manifest.get("name")``, and ``Ree`` has exactly one top-level key
    (``subject``). Every bundle downloaded as ``ree.zip`` — the fallback for an
    unnamed REE — so the failure looked like a design choice.
    """
    monkeypatch.setattr(command_dispatcher, "get_ree_manifest", lambda handle: _manifest("My Study"))

    assert archive_download_filename(online_ree) == "My_Study.zip"


def test_an_unnamed_ree_still_downloads(online_ree: ReeRoute, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fallback is for a genuinely blank name, which the domain permits."""
    monkeypatch.setattr(command_dispatcher, "get_ree_manifest", lambda handle: _manifest(""))

    assert archive_download_filename(online_ree) == "ree.zip"


# ================================================
# Listing projection
# ================================================


@pytest.fixture
def staged() -> Iterator[Callable[[list[tuple[str, Ree]]], None]]:
    """Stage REEs in a store as last seen, which is what listing reads; removed afterwards."""
    staged_ids: list[str] = []

    def stage(entries: list[tuple[str, Ree]]) -> None:
        for rid, manifest in entries:
            ree_registry.create(rid, manifest.subject.definition.name, "lab-test")
            ree_registry.update_summary(rid, name=manifest.subject.definition.name, status=ree_status(manifest))
            staged_ids.append(rid)

    yield stage
    for rid in staged_ids:
        ree_registry.delete(rid)


def test_listing_projects_name_and_status_from_the_parsed_document(
    client: TestClient, staged: Callable[[list[tuple[str, Ree]]], None]
) -> None:
    staged([("a1", _manifest("Alpha")), ("b2", _manifest("Beta", sealed=True))])

    items = client.get("/api/v1/rees").json()["items"]

    assert {item["name"]: item["status"] for item in items} == {"Alpha": "draft", "Beta": "sealed"}


def test_status_filter_reads_the_derived_status(
    client: TestClient, staged: Callable[[list[tuple[str, Ree]]], None]
) -> None:
    """``status`` is derived by core's ``ree_status``, not re-read from the seal.

    The projection used to decide this itself (``"sealed" if ree.get("seal")``),
    a second definition of what a seal means, in a package that may not know.
    """
    staged([("a1", _manifest("Alpha")), ("b2", _manifest("Beta", sealed=True))])

    items = client.get("/api/v1/rees", params={"status": "sealed"}).json()["items"]

    assert [item["name"] for item in items] == ["Beta"]

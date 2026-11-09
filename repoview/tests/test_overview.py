"""The overview reads its owners' exports and builds a whole bundle of this tree."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from repo2ree_repoview.overview.build import build
from repo2ree_repoview.overview.bundle import COMMAND, Bundle, sha256
from repo2ree_repoview.overview.exports import SPEC_EXPORT, ZONES_EXPORT, Spec, Zones, exported, operations_export
from repo2ree_repoview.overview.receipt import gate_verifications, read_receipt
from repo2ree_repoview.repository import ROOT, Provenance
from repo2ree_repoview.stamp import Stamp, record


@pytest.fixture
def exports(tmp_path: Path) -> Path:
    """The owners' exports as the recipes `just repo-overview` depends on write them."""
    directory = tmp_path / "exports"
    directory.mkdir()
    (directory / "spec.json").write_text(exported(SPEC_EXPORT))
    (directory / "zones.json").write_text(exported(ZONES_EXPORT))
    (directory / "operations.json").write_text(exported(operations_export(gate_verifications(read_receipt()))))
    (directory / "just-recipes.json").write_text(exported(("just", "--dump", "--dump-format", "json")))
    (directory / "showcases.json").write_text(
        exported((sys.executable, "-m", "repo2ree_testbed", "showcase-runs", "-o", "/dev/stdout"))
    )
    return directory


def test_the_exports_read_as_the_owners_wrote_them() -> None:
    spec_document = json.loads(exported(SPEC_EXPORT))
    spec = Spec.model_validate(spec_document)
    assert spec.digest == spec_document["digest"]
    assert list(spec.entities) == list(spec_document["entities"])
    assert [rule.id for rule in spec.invariants] == [rule["id"] for rule in spec_document["invariants"]]

    zones = Zones.model_validate_json(exported(ZONES_EXPORT))
    assert {placed.path: placed.zone for placed in zones.files}["repoview/tests/test_overview.py"] == "tooling"
    assert any(zone.protected for zone in zones.zones)


def test_a_document_in_another_format_is_refused() -> None:
    with pytest.raises(ValidationError, match=r"expected a repo2ree-behaviour-spec/1 document, got '.*/0'"):
        Spec.model_validate({"format": "repo2ree-behaviour-spec/0"})
    with pytest.raises(ValidationError, match="expected a repo2ree-zones/1 document, got None"):
        Zones.model_validate({})


def test_a_bundle_replaces_an_earlier_overview_but_nothing_else(tmp_path: Path) -> None:
    earlier = tmp_path / "earlier"
    earlier.mkdir()
    (earlier / "manifest.json").write_text(json.dumps({"command": COMMAND}))
    (earlier / "index.html").write_text("old")
    assert not any(Bundle(earlier, "a" * 40).root.iterdir())

    unrelated = tmp_path / "reports"
    unrelated.mkdir()
    (unrelated / "manifest.json").write_text(json.dumps({"graph.svg": {}}))
    with pytest.raises(FileExistsError, match="refusing to replace it"):
        Bundle(unrelated, "a" * 40)
    assert (unrelated / "manifest.json").is_file()


def test_the_overview_of_this_tree_is_a_whole_bundle(tmp_path: Path, exports: Path) -> None:
    target = build(tmp_path / "overview", exports)

    pages = {path.name for path in target.glob("*.html")}
    assert pages == {
        f"{name}.html"
        for name in (
            *("index", "zones", "assurance-gate", "receipts", "operations", "vocabulary", "specification", "coverage"),
            "showcase-gate",
            *("ree-machine", "architecture", "just-recipes", "configuration", "api"),
            # The frame its bundled evidence is shown in.
            "evidence",
        )
    }
    manifest = json.loads((target / "manifest.json").read_text())
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True)
    assert manifest["revision"] == head.stdout.strip()
    for entry in manifest["copied"]:
        assert sha256(target / entry["path"]) == entry["sha256"], entry["path"]
    owned = {"spec", "zones", "operations", "just-recipes", "showcases"}
    kinds = {entry["kind"]: entry["path"] for entry in manifest["copied"] if entry.get("kind") in owned}
    assert kinds == {kind: f"inputs/{kind}.json" for kind in owned}


def test_an_export_keeps_the_commit_its_recipe_stamped_it_with(tmp_path: Path, exports: Path) -> None:
    stamp = Stamp(**Provenance.now().model_dump(), by="export-spec")
    record(exports / "manifest.json", [exports / "spec.json"], stamp)
    manifest = json.loads((build(tmp_path / "overview", exports) / "manifest.json").read_text())
    revisions = {
        entry["kind"]: entry.get("revision") for entry in manifest["copied"] if entry["path"].startswith("inputs/")
    }
    assert revisions["spec"] == stamp.revision
    assert revisions["zones"] == ""


def test_an_overview_without_an_export_says_which_recipe_writes_it(tmp_path: Path, exports: Path) -> None:
    (exports / "operations.json").unlink()
    with pytest.raises(FileNotFoundError, match=r"operations\.json: missing; run just repo-overview"):
        build(tmp_path / "overview", exports)


def test_the_frame_shows_a_bundled_evidence_page_beside_the_sidebar(tmp_path: Path, exports: Path) -> None:
    target = build(tmp_path / "overview", exports)
    frame = (target / "evidence.html").read_text()
    assert '<iframe id="shown"' in frame
    # Every page of the overview, as its sidebar lists them, and none marked: the frame marks the one it came from.
    assert 'href="assurance-gate.html"' in frame
    assert 'class="current"' not in frame

"""The overview reads its owners' exports and builds a whole bundle of this tree."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from repo2ree_repoview.overview.build import build
from repo2ree_repoview.overview.bundle import COMMAND, Bundle, sha256
from repo2ree_repoview.overview.exports import SPEC_EXPORT, ZONES_EXPORT, Spec, Zones, exported
from repo2ree_repoview.repository import ROOT


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


def test_the_overview_of_this_tree_is_a_whole_bundle(tmp_path: Path) -> None:
    target = build(tmp_path / "overview")

    pages = {path.name for path in target.glob("*.html")}
    assert pages == {
        f"{name}.html"
        for name in (
            *("index", "zones", "assurance-gate", "operations", "vocabulary", "specification", "coverage"),
            *("ree-machine", "architecture", "just-recipes", "configuration", "api"),
        )
    }
    manifest = json.loads((target / "manifest.json").read_text())
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True)
    assert manifest["revision"] == head.stdout.strip()
    for entry in manifest["copied"]:
        assert sha256(target / entry["path"]) == entry["sha256"], entry["path"]
    exports = {"spec", "zones", "operations"}
    kinds = {entry["kind"]: entry["path"] for entry in manifest["copied"] if entry.get("kind") in exports}
    assert kinds == {kind: f"inputs/{kind}.json" for kind in exports}

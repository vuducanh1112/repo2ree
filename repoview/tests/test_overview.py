"""The overview reads its owners' exports and builds a whole bundle of this tree."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from repo2ree_repoview.overview.build import build
from repo2ree_repoview.overview.exports import read_spec, read_zones
from repo2ree_repoview.overview.inputs import SPEC_EXPORT, ZONES_EXPORT, exported, sha256
from repo2ree_repoview.repository import ROOT


def test_the_exports_read_as_the_owners_wrote_them() -> None:
    spec_document = json.loads(exported(SPEC_EXPORT))
    spec = read_spec(spec_document)
    assert spec.digest == spec_document["digest"]
    assert list(spec.entities) == list(spec_document["entities"])
    assert [rule.id for rule in spec.invariants] == [rule["id"] for rule in spec_document["invariants"]]
    assert all(rule.when.kind in {"entity", "message"} for rule in spec.invariants)

    zones = read_zones(json.loads(exported(ZONES_EXPORT)))
    assert zones.files["repoview/tests/test_overview.py"] == "tooling"
    assert any(zone.protected for zone in zones.zones)


def test_a_document_in_another_format_is_refused() -> None:
    with pytest.raises(ValueError, match="repo2ree-behaviour-spec/1"):
        read_spec({"format": "repo2ree-behaviour-spec/0"})
    with pytest.raises(ValueError, match="repo2ree-zones/1"):
        read_zones({})


def test_the_overview_of_this_tree_is_a_whole_bundle(tmp_path: Path) -> None:
    target = build(tmp_path / "overview")

    pages = {path.name for path in target.glob("*.html")}
    assert pages == {
        f"{name}.html"
        for name in (
            *("index", "zones", "behaviour-gate", "vocabulary", "specification", "coverage"),
            *("architecture", "just-recipes", "configuration", "api"),
        )
    }
    manifest = json.loads((target / "manifest.json").read_text())
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True)
    assert manifest["revision"] == head.stdout.strip()
    for entry in manifest["copied"]:
        assert sha256(target / entry["path"]) == entry["sha256"], entry["path"]
    kinds = {entry["kind"]: entry["path"] for entry in manifest["copied"] if entry.get("kind") in {"spec", "zones"}}
    assert kinds == {"spec": "inputs/spec.json", "zones": "inputs/zones.json"}

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from repo2ree_repoview.overview.bundle import COMMAND, Bundle
from repo2ree_repoview.overview.exports import (
    SPEC_EXPORT,
    ZONES_EXPORT,
    Spec,
    Zones,
    exported,
)


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

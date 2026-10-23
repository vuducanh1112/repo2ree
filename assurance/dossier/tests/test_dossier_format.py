"""A dossier's manifest round-trips, and anything else is refused with the directory named."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_assurance_dossier import Dossier, DossierContext, DossierSource, read_dossier, write_dossier


def test_a_manifest_round_trips_with_origins_cuts_and_problems(tmp_path: Path) -> None:
    dossier = Dossier(
        control_plane="http://cp",
        context=DossierContext(suite="demo-gui", outcome="passed"),
        sources=(
            DossierSource(kind="journal", path="journal", origin="http://cp/api/v1/behaviour/journals"),
            DossierSource(kind="git", path="rees/r/ree", origin="http://cp/archive", cut={"api-000001": (3, 5)}),
            DossierSource(kind="spans", path="telemetry/api.ndjson", origin="x", status="error", problem="gone"),
        ),
    )
    write_dossier(tmp_path, dossier)
    assert read_dossier(tmp_path) == dossier
    assert [source.path for source in dossier.recorded("git")] == ["rees/r/ree"]
    assert dossier.recorded("spans") == []


def test_adding_a_source_at_the_same_path_replaces_it() -> None:
    first = DossierSource(kind="git", path="rees/r/ree", origin="a", status="error")
    second = first.model_copy(update={"status": "recorded"})
    assert Dossier().with_source(first).with_source(second).sources == (second,)


@pytest.mark.parametrize(
    ("manifest", "problem"), [(None, "no manifest.json"), ('{"repositories": []}', "not a dossier manifest")]
)
def test_anything_else_is_refused_naming_the_directory(tmp_path: Path, manifest: str | None, problem: str) -> None:
    if manifest is not None:
        (tmp_path / "manifest.json").write_text(manifest)
    with pytest.raises(ValueError, match=problem):
        read_dossier(tmp_path)

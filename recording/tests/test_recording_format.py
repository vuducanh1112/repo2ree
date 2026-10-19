"""A recording's manifest round-trips, and anything else is refused with the directory named."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_recording import RecordedSource, Recording, RecordingContext, read_recording, write_recording


def test_a_manifest_round_trips_with_origins_cuts_and_problems(tmp_path: Path) -> None:
    recording = Recording(
        control_plane="http://cp",
        context=RecordingContext(suite="demo-gui", outcome="passed"),
        sources=(
            RecordedSource(kind="journal", path="journal", origin="http://cp/api/v1/behaviour/journals"),
            RecordedSource(kind="git", path="rees/r/ree", origin="http://cp/archive", cut={"api-000001": (3, 5)}),
            RecordedSource(kind="spans", path="telemetry/api.ndjson", origin="x", status="error", problem="gone"),
        ),
    )
    write_recording(tmp_path, recording)
    assert read_recording(tmp_path) == recording
    assert [source.path for source in recording.recorded("git")] == ["rees/r/ree"]
    assert recording.recorded("spans") == []


def test_adding_a_source_at_the_same_path_replaces_it() -> None:
    first = RecordedSource(kind="git", path="rees/r/ree", origin="a", status="error")
    second = first.model_copy(update={"status": "recorded"})
    assert Recording().with_source(first).with_source(second).sources == (second,)


@pytest.mark.parametrize(
    ("manifest", "problem"), [(None, "no manifest.json"), ('{"repositories": []}', "not a recording manifest")]
)
def test_anything_else_is_refused_naming_the_directory(tmp_path: Path, manifest: str | None, problem: str) -> None:
    if manifest is not None:
        (tmp_path / "manifest.json").write_text(manifest)
    with pytest.raises(ValueError, match=problem):
        read_recording(tmp_path)

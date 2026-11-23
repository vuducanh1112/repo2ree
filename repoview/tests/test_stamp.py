from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo2ree_repoview.stamp import (
    Stamp,
    StampConflictError,
    read_recorded_stamp,
    read_svg_stamp,
    record,
    stamp_svg,
)

FACTS = Stamp(
    revision="a" * 40,
    tree="b" * 40,
    dirty=False,
    working_tree_sha256=None,
    generated="2026-10-20T15:16:24+00:00",
    by="generate-gui-graph",
)


GENERATED = '<?xml version="1.0"?>\n<svg width="200pt" height="100pt"\n viewBox="0.00 0.00 200.00 100.00"><g/></svg>\n'


def test_an_svg_shows_its_commit_below_the_drawing_and_carries_the_facts(tmp_path: Path) -> None:
    svg = tmp_path / "graph.svg"
    svg.write_text(GENERATED)
    assert read_svg_stamp(svg) is None

    stamp_svg(svg, FACTS.model_copy(update={"dirty": True}))

    stamped = svg.read_text()
    assert read_svg_stamp(svg) == FACTS.model_copy(update={"dirty": True})
    assert "repo2ree aaaaaaaaaa + uncommitted changes · 2026-10-20 15:16:24 UTC · generate-gui-graph" in stamped
    assert 'viewBox="0 0 200 118"' in stamped
    assert 'height="118pt"' in stamped
    assert stamped.index("<g/>") < stamped.index("repo2ree-stamp")


def test_a_restamp_replaces_the_stamp_and_restores_the_size_first(tmp_path: Path) -> None:
    svg = tmp_path / "graph.svg"
    svg.write_text(GENERATED)
    stamp_svg(svg, FACTS)
    restamp = FACTS.model_copy(update={"revision": "c" * 40, "by": "a <quoted> & recipe"})
    stamp_svg(svg, restamp)

    stamped = svg.read_text()
    assert read_svg_stamp(svg) == restamp
    assert stamped.count("repo2ree-provenance") == 1
    assert stamped.count("repo2ree-stamp") == 1
    assert 'viewBox="0 0 200 118"' in stamped
    assert "a &lt;quoted&gt; &amp; recipe" in stamped


def test_each_recipe_writes_a_stamp_file_of_its_own_naming_each_file_by_its_path_in_the_folder(
    tmp_path: Path,
) -> None:
    (tmp_path / "architecture").mkdir()
    first, second = tmp_path / "architecture/a.svg", tmp_path / "b.csv"
    first.write_text("<svg></svg>")
    second.write_text("x,y\n")

    record(tmp_path, [first], FACTS)
    record(tmp_path, [second], FACTS.model_copy(update={"by": "generate-metrics", "dirty": True}))

    graph = json.loads((tmp_path / "stamps/generate-gui-graph.json").read_text())
    metrics = json.loads((tmp_path / "stamps/generate-metrics.json").read_text())
    assert set(graph) == {"architecture/a.svg"}
    assert set(metrics) == {"b.csv"}
    assert metrics["b.csv"]["dirty"] is True
    assert len(metrics["b.csv"]["sha256"]) == 64


def test_a_recipe_s_stamp_file_holds_only_what_it_generated_last(tmp_path: Path) -> None:
    first, second = tmp_path / "a.svg", tmp_path / "b.svg"
    first.write_text("<svg></svg>")
    second.write_text("<svg/>")

    record(tmp_path, [first], FACTS)
    record(tmp_path, [second], FACTS)

    assert set(json.loads((tmp_path / "stamps/generate-gui-graph.json").read_text())) == {"b.svg"}
    assert read_recorded_stamp(first) is None


def test_a_file_reads_its_stamp_from_its_report_folder_only_as_it_was_stamped(tmp_path: Path) -> None:
    (tmp_path / "spec").mkdir()
    export, nested = tmp_path / "spec.json", tmp_path / "spec/ree.svg"
    export.write_text("{}")
    nested.write_text("<svg/>")
    assert read_recorded_stamp(export) is None

    record(tmp_path, [export, nested], FACTS)
    assert read_recorded_stamp(export) == FACTS
    assert read_recorded_stamp(nested) == FACTS, "a file in a subfolder reads its report folder's stamps"

    export.write_text('{"changed": true}')
    assert read_recorded_stamp(export) is None


def test_two_recipes_that_stamp_one_file_are_an_error(tmp_path: Path) -> None:
    export = tmp_path / "spec.json"
    export.write_text("{}")
    record(tmp_path, [export], FACTS)
    record(tmp_path, [export], FACTS.model_copy(update={"by": "export-spec"}))

    with pytest.raises(StampConflictError, match="export-spec, generate-gui-graph"):
        read_recorded_stamp(export)


def test_a_recipe_that_skips_what_is_current_keeps_those_files_stamps(tmp_path: Path) -> None:
    kept, renewed, gone = tmp_path / "a.mp4", tmp_path / "b.mp4", tmp_path / "c.mp4"
    for path in (kept, renewed, gone):
        path.write_bytes(path.name.encode())
    first = FACTS.model_copy(update={"by": "render-cli-sessions"})
    record(tmp_path, [kept, renewed, gone], first)
    gone.unlink()
    renewed.write_bytes(b"rendered again")
    later = first.model_copy(update={"revision": "c" * 40})

    record(tmp_path, [renewed], later, keep=True)

    assert read_recorded_stamp(kept) == first, "a file the recipe kept keeps the commit that made it"
    assert read_recorded_stamp(renewed) == later
    assert set(json.loads((tmp_path / "stamps/render-cli-sessions.json").read_text())) == {"a.mp4", "b.mp4"}

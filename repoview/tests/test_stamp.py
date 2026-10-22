from __future__ import annotations

import json
from pathlib import Path

from repo2ree_repoview.stamp import read_svg_stamp, record, stamp_svg

FACTS = {"revision": "a" * 40, "tree": "b" * 40, "dirty": False, "by": "generate-gui-graph"}


GENERATED = '<?xml version="1.0"?>\n<svg width="200pt" height="100pt"\n viewBox="0.00 0.00 200.00 100.00"><g/></svg>\n'


def test_an_svg_shows_its_commit_below_the_drawing_and_carries_the_facts(tmp_path: Path) -> None:
    svg = tmp_path / "graph.svg"
    svg.write_text(GENERATED)
    assert read_svg_stamp(svg) is None

    stamp_svg(svg, FACTS | {"dirty": True, "generated": "2026-10-20T15:16:24+00:00"})

    stamped = svg.read_text()
    assert read_svg_stamp(svg) == FACTS | {"dirty": True, "generated": "2026-10-20T15:16:24+00:00"}
    assert "repo2ree aaaaaaaaaa + uncommitted changes · 2026-10-20 15:16:24 UTC · generate-gui-graph" in stamped
    # The strip is added below the drawing: the canvas grows, nothing is drawn over the graph.
    assert 'viewBox="0 0 200 118"' in stamped
    assert 'height="118pt"' in stamped
    assert stamped.index("<g/>") < stamped.index("repo2ree-stamp")


def test_a_restamp_replaces_the_stamp_and_restores_the_size_first(tmp_path: Path) -> None:
    svg = tmp_path / "graph.svg"
    svg.write_text(GENERATED)
    stamp_svg(svg, FACTS)
    stamp_svg(svg, FACTS | {"revision": "c" * 40, "by": "a <quoted> & recipe"})

    stamped = svg.read_text()
    assert read_svg_stamp(svg) == FACTS | {"revision": "c" * 40, "by": "a <quoted> & recipe"}
    assert stamped.count("repo2ree-provenance") == 1
    assert stamped.count("repo2ree-stamp") == 1
    assert 'viewBox="0 0 200 118"' in stamped
    assert "a &lt;quoted&gt; &amp; recipe" in stamped


def test_the_manifest_keeps_other_files_and_names_each_by_its_path_in_the_folder(tmp_path: Path) -> None:
    (tmp_path / "architecture").mkdir()
    first, second = tmp_path / "architecture/a.svg", tmp_path / "b.csv"
    first.write_text("<svg></svg>")
    second.write_text("x,y\n")
    manifest = tmp_path / "manifest.json"

    record(manifest, [first], FACTS)
    record(manifest, [second], FACTS | {"dirty": True})

    entries = json.loads(manifest.read_text())
    assert set(entries) == {"architecture/a.svg", "b.csv"}
    assert entries["architecture/a.svg"]["dirty"] is False
    assert entries["b.csv"]["dirty"] is True
    assert len(entries["b.csv"]["sha256"]) == 64

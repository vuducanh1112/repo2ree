"""Recorded views preserve evidence and can be rendered repeatedly without I/O."""

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from repo2ree_history.core import ree_filmstrip as filmstrip
from repo2ree_history.core import trace_journal as journal
from repo2ree_history.shell.cli import main


def span(name, span_id, parent=None, trace="trace"):
    return journal.Span(name, span_id, parent, trace, "api", 0, 1000, {}, "OK")


def test_journal_rendering_is_repeatable_and_does_not_mutate_inputs(monkeypatch):
    spans = [span("root", "1"), span("noise", "2", "1"), span("child", "3", "2")]
    original = copy.deepcopy(spans)

    def forbidden(*args, **kwargs):
        pytest.fail("rendering attempted I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    kept = journal.prune(spans, ["noise"], [])
    assert kept[1].parent_id == "1"
    groups = journal.collect_groups({"trace": kept}, "trace")
    again = journal.collect_groups({"trace": kept}, "trace")
    assert groups == again
    assert spans == original
    assert not kept[0].children
    scale = journal.build_scale(groups)
    assert journal.render_svg(groups, scale, shapes=True) == journal.render_svg(again, scale, shapes=True)
    assert "<svg" in journal.render_graph_page('<svg width="10pt" height="10pt"></svg>', title="test")


def test_parent_and_link_ids_are_scoped_to_their_trace():
    a = span("a-root", "1", trace="a")
    b = span("b-root", "1", trace="b")
    child = span("a-child", "2", "1", trace="a")
    child.links = [("b", "1")]
    roots = journal.build_forest([a, b, child])
    assert [(root.name, [s.name for s in root.children]) for root in roots] == [("a-root", ["a-child"]), ("b-root", [])]
    dot = journal.render_dot([a, b, child], notes=False, merged=False, zones=[])
    assert f'"{journal.node_key(b)}" -> "{journal.node_key(child)}" [style=dashed' in dot


def test_span_parser_skips_non_spans_and_preserves_microseconds():
    raw: dict[str, Any] = {
        "name": "request",
        "context": {"trace_id": "0xa", "span_id": "0xb"},
        "start_time": "2026-09-15T00:00:00.000001+00:00",
        "end_time": "2026-09-15T00:00:00.000002+00:00",
    }
    spans = journal.parse_spans("invalid\n[]\n{}\n" + json.dumps(raw))
    assert len(spans) == 1
    assert spans[0].end_ns - spans[0].start_ns == 1000
    assert spans[0].span_id == "b"
    raw["start_time"] = "2026-09-15T00:00:00"
    with pytest.raises(ValueError, match="timezone"):
        journal.parse_spans(json.dumps(raw))


def test_filmstrip_derives_receipt_changes_without_mutating_frames():
    raw: dict[str, Any] = {
        "label": "declared",
        "state": {
            "audit": {s: {"evidence": "missing"} for s in filmstrip.STEP_FIELDS},
            "ree": {"subject": {"receipts": {"source": None}}},
        },
    }
    first = json.dumps(raw)
    raw["label"] = "ran"
    raw["state"]["ree"]["subject"]["receipts"]["source"] = {"run_id": "run-1"}
    frames = filmstrip.parse_frames(first + "\n" + json.dumps(raw))
    before = copy.deepcopy(frames)
    assert [f.produced_receipt for f in frames] == [False, True]
    assert "<svg" in filmstrip.render_svg(frames, filmstrip.build_rows(frames))
    assert filmstrip.diff_frames(frames)
    assert frames == before


@pytest.mark.parametrize("view_format", ["matrix", "timeline", "browse"])
def test_empty_capture_fails_cleanly_without_output(tmp_path, capsys, view_format):
    capture = tmp_path / "state.ndjson"
    capture.write_text("")
    output = tmp_path / "view.html"
    assert main(["ree-filmstrip", "--frames", str(capture), "-f", view_format, "-o", str(output)]) == 1
    assert "no frames" in capsys.readouterr().err
    assert not output.exists()

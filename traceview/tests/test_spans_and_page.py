"""Spans are read as the e2e stack writes them, and a trace renders into one self-contained page."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from repo2ree_traceview.cli import main
from repo2ree_traceview.files import template
from repo2ree_traceview.model import Entry, OperationTrace, Recording
from repo2ree_traceview.render import PLACEHOLDER, render_html
from repo2ree_traceview.spans import SpanIndex, parse_spans

ROOT = Path(__file__).resolve().parents[2]
RECORDINGS = ROOT / "test-artifacts" / "recordings"


def exported(span_id: str, parent: str | None, start: str, end: str, **extra: object) -> dict[str, object]:
    return {
        "name": extra.pop("name", "run.build"),
        "context": {"trace_id": "0x" + "a" * 32, "span_id": f"0x{span_id}"},
        "kind": "SpanKind.INTERNAL",
        "parent_id": f"0x{parent}" if parent else None,
        "start_time": start,
        "end_time": end,
        "status": {"status_code": "UNSET"},
        "attributes": {"repo2ree.operation": "build"},
        "events": [{"name": "repo2ree.result", "timestamp": end, "attributes": {"repo2ree.boundary": "api.finalized"}}],
        "resource": {"attributes": {"service.name": "repo2ree-api"}},
        **extra,
    }


def test_console_exporter_output_is_read_as_spans() -> None:
    # The exporter writes indented objects back to back, not one per line.
    text = "\n".join(
        json.dumps(document, indent=4)
        for document in (
            exported("01", None, "2026-10-18T10:00:00.000000Z", "2026-10-18T10:00:02.000000Z"),
            exported("02", "01", "2026-10-18T10:00:00.500000Z", "2026-10-18T10:00:01.000000Z", name="process.exec"),
        )
    )
    first, second = parse_spans(text)
    assert (first.id, first.parent, first.service, first.kind, first.duration) == ("01", None, "api", "INTERNAL", 2.0)
    assert first.events[0].attributes == {"repo2ree.boundary": "api.finalized"}
    assert SpanIndex([first, second]).children(first) == [second]


def test_a_rendered_page_carries_its_trace_and_cannot_be_broken_out_of() -> None:
    trace = OperationTrace(
        recording=Recording(name="</script><script>alert(1)</script>"),
        ree="ree-1",
        spec_digest="sha256:" + "0" * 64,
        verdict="passed",
        sealed=False,
        duration=1.0,
        sources=(),
        entries=(Entry(kind="operation", name="build_runtime", start=0.0, end=1.0),),
        steps=(),
        standings=(),
    )
    page = render_html(trace, template())
    assert PLACEHOLDER not in page
    assert "</script><script>alert" not in page
    assert page.startswith("<!doctype html>")


def test_a_template_without_a_place_for_the_trace_is_refused() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        render_html(OperationTrace.model_construct(), "<html></html>")


def recordings() -> list[Path]:
    if not RECORDINGS.is_dir():
        return []
    return [
        path for path in sorted(RECORDINGS.iterdir()) if (path / "journal").is_dir() and (path / "capture").is_dir()
    ]


@pytest.mark.skipif(shutil.which("git") is None or not recordings(), reason="needs git and a recording with journals")
def test_a_real_recording_draws_one_page_per_ree(tmp_path: Path) -> None:
    assert main([str(recordings()[0]), "-o", str(tmp_path), "--json", "--provenance"]) == 0
    pages = sorted(tmp_path.glob("*.html"))
    assert pages
    for page in pages:
        trace = OperationTrace.model_validate_json(page.with_suffix(".json").read_text())
        assert page.stem == trace.ree
        assert all(entry.sequence and entry.sequence.rows for entry in trace.entries if entry.kind == "operation")
        assert PLACEHOLDER not in page.read_text()
        assert page.with_suffix(".provenance.txt").exists()

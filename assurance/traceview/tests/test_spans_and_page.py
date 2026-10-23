"""Spans are read as the e2e stack writes them, and a trace renders into one self-contained page."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from repo2ree_assurance_dossier import read_dossier
from repo2ree_assurance_traceview.cli import main
from repo2ree_assurance_traceview.files import template
from repo2ree_assurance_traceview.model import BehaviourTrace, DossierInfo, Entry
from repo2ree_assurance_traceview.render import PLACEHOLDER, render_html
from repo2ree_assurance_traceview.spans import SpanIndex, parse_spans

ROOT = Path(__file__).resolve().parents[3]
E2E_RUNS = ROOT / "test-artifacts" / "e2e"


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
    (first, second), unreadable = parse_spans(text)
    assert unreadable == 0
    assert (first.id, first.parent, first.service, first.kind, first.duration) == ("01", None, "api", "INTERNAL", 2.0)
    assert first.events[0].attributes == {"repo2ree.boundary": "api.finalized"}
    assert SpanIndex([first, second]).children(first) == [second]


def test_span_records_that_cannot_be_read_are_counted_and_passed_over() -> None:
    whole = json.dumps(exported("01", None, "2026-10-18T10:00:00Z", "2026-10-18T10:00:01Z"), indent=4)
    unfinished = exported("02", None, "2026-10-18T10:00:00Z", "2026-10-18T10:00:01Z")
    del unfinished["end_time"]
    cut = json.dumps(exported("03", None, "2026-10-18T10:00:00Z", "2026-10-18T10:00:01Z"), indent=4)[:-40]
    # A record without its end, one cut short by a killed process, and readable ones around them.
    text = "\n".join([whole, json.dumps(unfinished, indent=4), cut, whole.replace("0x01", "0x04")])
    spans, unreadable = parse_spans(text)
    assert [span.id for span in spans] == ["01", "04"]
    assert unreadable == 2


def test_a_rendered_page_carries_its_trace_and_cannot_be_broken_out_of() -> None:
    trace = BehaviourTrace(
        dossier=DossierInfo(name="</script><script>alert(1)</script> <!--<script>"),
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
    assert "<!--<script>" not in page
    embedded = page.split("const TRACE = ", 1)[1].split(";\n", 1)[0]
    assert json.loads(embedded)["dossier"]["name"] == "</script><script>alert(1)</script> <!--<script>"
    assert page.startswith("<!doctype html>")


def test_a_template_without_a_place_for_the_trace_is_refused() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        render_html(BehaviourTrace.model_construct(), "<html></html>")


def dossiers() -> list[Path]:
    """Dossiers holding journals and at least one REE's history: a test that failed early may leave none."""
    found: list[Path] = []
    for path in sorted(E2E_RUNS.glob("*/tests/*/dossier")):
        try:
            dossier = read_dossier(path)
            if dossier.recorded("journal") and dossier.recorded("git"):
                found.append(path)
        except (OSError, ValueError):
            continue  # Not a dossier in the current format.
    return found


@pytest.mark.skipif(not dossiers(), reason="needs an e2e run's dossier with an REE under test-artifacts/e2e")
def test_a_real_recording_draws_one_page_per_ree(tmp_path: Path) -> None:
    # Verification is its own step; the views read only what it wrote.
    verified = tmp_path / "verified"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "repo2ree_assurance_checker",
            "check",
            "--dossier",
            str(dossiers()[0]),
            "-o",
            str(verified),
        ],
        check=False,
        capture_output=True,
    )
    pages_dir = tmp_path / "pages"
    assert main([str(verified), "-o", str(pages_dir), "--json", "--provenance"]) == 0
    pages = sorted(pages_dir.glob("*.html"))
    assert pages
    for page in pages:
        trace = BehaviourTrace.model_validate_json(page.with_suffix(".json").read_text())
        assert page.stem == trace.ree
        assert all(entry.sequence and entry.sequence.rows for entry in trace.entries if entry.kind == "operation")
        assert PLACEHOLDER not in page.read_text()
        assert page.with_suffix(".provenance.txt").exists()


def test_the_command_line_says_what_it_cannot_draw(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "absent"), "--output", str(tmp_path / "out")]) == 2
    assert "not a verification" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main([str(tmp_path / "absent")])  # Nothing to write.
    with pytest.raises(SystemExit):
        main([str(tmp_path / "absent"), "--json"])  # --json needs --output.

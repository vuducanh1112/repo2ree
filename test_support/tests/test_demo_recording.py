"""Demo preservation survives workbench release and keeps capture provenance."""

import json
from pathlib import Path

from test_support import demo_recording


def test_preserve_reuses_pre_release_repository(tmp_path, monkeypatch):
    manifest = {"repositories": [{"status": "recorded", "path": "capture/rees/bench"}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    def forbidden(*args, **kwargs):
        raise AssertionError("must not recapture a released workbench")

    monkeypatch.setattr(demo_recording, "TestRecorder", forbidden)
    demo_recording.preserve(tmp_path)
    assert json.loads((tmp_path / "manifest.json").read_text()) == manifest


def test_finish_keeps_sources_and_merges_only_owned_trace_files(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"repositories": [], "runtime": "node"}))
    (tmp_path / "telemetry").mkdir()
    first = '{"name":"api"}\n'
    second = '{"name":"provider"}\n'
    (tmp_path / "telemetry/api.ndjson").write_text(first)
    (tmp_path / "telemetry/provider.ndjson").write_text(second)
    demo_recording.finish(tmp_path, "passed")
    assert (tmp_path / "traces.ndjson").read_text().split() == [first.strip(), second.strip()]
    assert json.loads((tmp_path / "manifest.json").read_text())["outcome"] == "passed"
    assert Path(tmp_path / "telemetry/api.ndjson").read_text() == first

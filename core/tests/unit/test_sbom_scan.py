"""The scanner runs through the shared process runner, not a blocking call."""

from pathlib import Path
from typing import Any

import pytest

from repo2ree_core.analysis.sbom import scan as scan_module
from repo2ree_core.analysis.sbom.scan import ScanOutcome, is_runtime_archive, scan_runtime_archive
from repo2ree_core.execution.process import StreamingProcessResult


@pytest.fixture
def fake_syft(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Capture what the scanner would have run, without running anything."""
    seen: dict[str, Any] = {}
    monkeypatch.setattr(scan_module, "resolve_tool", lambda _name: "/usr/bin/syft")

    def runner(cmd: list[str], **kwargs: Any) -> StreamingProcessResult:
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        result: StreamingProcessResult = seen.get("result", StreamingProcessResult(returncode=0, stdout="", stderr=""))
        if writer := seen.get("writer"):
            writer()
        return result

    monkeypatch.setattr(scan_module, "run_streaming_process", runner)
    return seen


def test_cancel_check_reaches_the_process_runner(fake_syft: dict[str, Any], tmp_path: Path) -> None:
    """The whole point: a cancel must be able to stop a scan mid-flight."""

    def never() -> bool:
        return False

    scan_runtime_archive(tmp_path / "rt.tar", tmp_path / "sbom.json", log=lambda *_: None, is_canceled=never)
    assert fake_syft["kwargs"]["is_canceled"] is never


def test_scope_stays_pinned_to_squashed(fake_syft: dict[str, Any], tmp_path: Path) -> None:
    """Both sides must mean the same thing by 'observed in the runtime'."""
    scan_runtime_archive(tmp_path / "rt.tar", tmp_path / "sbom.json", log=lambda *_: None)
    cmd = fake_syft["cmd"]
    assert cmd[cmd.index("--scope") + 1] == "squashed"


def test_a_canceled_scan_is_not_reported_as_a_failed_one(fake_syft: dict[str, Any], tmp_path: Path) -> None:
    """A killed scanner exits nonzero like a broken one; only one is news."""
    fake_syft["result"] = StreamingProcessResult(returncode=-15, stdout="", stderr="", canceled=True)
    outcome = scan_runtime_archive(tmp_path / "rt.tar", tmp_path / "sbom.json", log=lambda *_: None)
    assert outcome.canceled
    assert outcome.tool_version is None


def test_a_cancel_arriving_after_the_scanner_exited_still_counts(fake_syft: dict[str, Any], tmp_path: Path) -> None:
    """The runner did not see it, but the caller must not settle a verdict."""
    fake_syft["result"] = StreamingProcessResult(returncode=0, stdout="", stderr="")
    outcome = scan_runtime_archive(
        tmp_path / "rt.tar", tmp_path / "sbom.json", log=lambda *_: None, is_canceled=lambda: True
    )
    assert outcome.canceled


def test_a_failed_scan_reports_its_exit_code_and_no_tool_version(fake_syft: dict[str, Any], tmp_path: Path) -> None:
    fake_syft["result"] = StreamingProcessResult(returncode=2, stdout="", stderr="boom")
    outcome = scan_runtime_archive(tmp_path / "rt.tar", tmp_path / "sbom.json", log=lambda *_: None)
    assert outcome == ScanOutcome(returncode=2, tool_version=None, canceled=False)


def test_a_successful_scan_reads_the_tool_version_off_the_document(fake_syft: dict[str, Any], tmp_path: Path) -> None:
    output = tmp_path / "sbom.json"
    fake_syft["writer"] = lambda: output.write_text(
        '{"metadata": {"tools": {"components": [{"name": "syft", "version": "1.2.3"}]}}}',
        encoding="utf-8",
    )
    outcome = scan_runtime_archive(tmp_path / "rt.tar", output, log=lambda *_: None)
    assert outcome.returncode == 0
    assert outcome.tool_version == "1.2.3"


def test_scanner_output_is_streamed_not_captured_and_replayed(fake_syft: dict[str, Any], tmp_path: Path) -> None:
    """The runner owns the log lines, so nothing is buffered until the end."""
    scan_runtime_archive(tmp_path / "rt.tar", tmp_path / "sbom.json", log=lambda *_: None)
    assert "log" in fake_syft["kwargs"]


@pytest.mark.parametrize(
    ("path", "expected"),
    [("rt.tar", True), ("rt.tar.gz", True), ("rt.TGZ", True), ("rt.zip", False), ("rt", False)],
)
def test_recognizes_the_archive_shapes_the_scanner_consumes(path: str, expected: bool) -> None:
    assert is_runtime_archive(path) is expected

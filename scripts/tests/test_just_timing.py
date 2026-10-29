import io
import json
import signal
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from scripts import just_timing as timing


@pytest.fixture
def signals() -> Iterator[None]:
    """The handlers a recording installs in this process, put back afterwards."""
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


def records(directory: Path) -> list[dict[str, Any]]:
    [path] = directory.rglob("*.jsonl")
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_only_commands_that_run_recipes_are_recorded() -> None:
    assert timing.runs_recipes(["commit-gate"])
    assert timing.runs_recipes(["--color=always", "test-e2e-faults", "4"])
    assert timing.runs_recipes(["echo", "--", "--list"])
    for listing in (["--list"], ["-l"], ["--dump", "--dump-format", "json"], ["--dry-run", "check"], ["--version"]):
        assert not timing.runs_recipes(listing), listing


def test_a_completed_recipe_is_read_from_the_line_just_prints_plain_or_coloured() -> None:
    assert timing.completed("---> test-unit-package completed in 62.845s\n") == ("test-unit-package", 62.845)
    assert timing.completed("\x1b[1m---> _e2e-faults completed in 201.0s\x1b[0m\r\n") == ("_e2e-faults", 201.0)
    assert timing.completed("---> tier completed in soon") is None
    assert timing.completed("error: recipe `check` failed") is None


class Shown(io.BytesIO):
    """A terminal that goes away after ``lasts`` writes."""

    def __init__(self, lasts: int) -> None:
        super().__init__()
        self.lasts = lasts

    def write(self, data: Any) -> int:
        if self.lasts == 0:
            raise BrokenPipeError
        self.lasts -= 1
        return super().write(data)


class Chunks(io.RawIOBase):
    def __init__(self, *chunks: bytes) -> None:
        self.chunks = list(chunks)

    def read1(self, _size: int = -1) -> bytes:
        return self.chunks.pop(0) if self.chunks else b""


def test_output_passes_through_unchanged_and_each_completed_recipe_is_recorded(tmp_path: Path) -> None:
    recorder = timing.Recorder(tmp_path / "day" / "run.jsonl")
    shown = Shown(lasts=10)
    chunks = Chunks(b"error: one\n---> bui", b"ld completed in 1.5s\n---> gate comp", b"leted in 2s\n")
    timing.forward(chunks, shown, recorder)
    recorder.close()
    assert shown.getvalue() == b"error: one\n---> build completed in 1.5s\n---> gate completed in 2s\n"
    assert [(r["recipe"], r["seconds"]) for r in records(tmp_path)] == [("build", 1.5), ("gate", 2.0)]


def test_a_terminal_that_goes_away_is_still_drained_and_recorded(tmp_path: Path) -> None:
    recorder = timing.Recorder(tmp_path / "day" / "run.jsonl")
    timing.forward(Chunks(b"first\n", b"---> late completed in 3s\n"), Shown(lasts=1), recorder)
    recorder.close()
    assert [r["recipe"] for r in records(tmp_path)] == ["late"]


def test_a_record_that_cannot_be_written_is_warned_about_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "day").write_text("a file where the day's directory would go")
    recorder = timing.Recorder(tmp_path / "day" / "run.jsonl")
    recorder.write({"kind": "start"})
    recorder.write({"kind": "end"})
    assert capsys.readouterr().err.count("just timings are not recorded") == 1


def test_days_older_than_kept_are_removed(tmp_path: Path) -> None:
    for day in ("2026-09-28", "2026-09-29", "2026-10-29"):
        (tmp_path / day).mkdir()
    (tmp_path / "notes").mkdir()
    today = datetime(2026, 10, 29, tzinfo=UTC)
    assert timing.prune(tmp_path, today, dry_run=True) == [tmp_path / "2026-09-28"]
    assert (tmp_path / "2026-09-28").exists()
    timing.prune(tmp_path, today)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["2026-09-29", "2026-10-29", "notes"]


def test_a_just_inside_a_recording_hands_over_to_the_real_one(monkeypatch: pytest.MonkeyPatch) -> None:
    handed: list[list[str]] = []

    def plainly(real: str, args: list[str]) -> None:
        handed.append([real, *args])
        raise SystemExit(0)

    monkeypatch.setattr(timing, "run_plainly", plainly)
    monkeypatch.setattr(timing, "record", lambda *_: pytest.fail("a nested just must not record"))
    monkeypatch.setenv(timing.MARKER, "/somewhere/run.jsonl")
    with pytest.raises(SystemExit):
        timing.main(["just_timing.py", "/real/just", "_e2e-faults", "4", "run"])
    monkeypatch.delenv(timing.MARKER)
    with pytest.raises(SystemExit):
        timing.main(["just_timing.py", "/real/just", "--list"])
    assert handed == [["/real/just", "_e2e-faults", "4", "run"], ["/real/just", "--list"]]


def test_an_invocation_is_recorded_from_start_to_end_with_justs_own_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str], signals: None
) -> None:
    fake = tmp_path / "just"
    fake.write_text(
        "#!/bin/sh\n"
        'echo "$JUST_TIME $REPO2REE_TEST_RUN_ID $*" > "$(dirname "$0")/seen"\n'
        "echo 'on stdout'\n"
        "echo '---> build-e2e-bundles completed in 18.4s' >&2\n"
        "printf '\\033[1m---> assurance-gate completed in 352.7s\\033[0m\\n' >&2\n"
        "exit 3\n"
    )
    fake.chmod(0o755)
    monkeypatch.setattr(timing, "LOGS", tmp_path / "logs")
    monkeypatch.setenv("REPO2REE_TEST_RUN_ID", "the-invocation")
    monkeypatch.setenv("REPO2REE_MACHINE", "vm")

    assert timing.record(str(fake), ["assurance-gate", "4"]) == 3

    start, *recipes, end = records(tmp_path / "logs")
    assert start["schema"] == timing.SCHEMA
    assert (start["kind"], start["invocation"], start["argv"], start["machine"]) == (
        "start",
        "the-invocation",
        ["assurance-gate", "4"],
        "vm",
    )
    assert [(r["recipe"], r["seconds"]) for r in recipes] == [("build-e2e-bundles", 18.4), ("assurance-gate", 352.7)]
    assert (end["kind"], end["exit"]) == ("end", 3)
    # just ran as asked, timing on, in this invocation; its output reached the terminal unchanged.
    assert (tmp_path / "seen").read_text() == "true the-invocation assurance-gate 4\n"
    captured = capfd.readouterr()
    assert captured.out == "on stdout\n"
    assert "---> build-e2e-bundles completed in 18.4s" in captured.err

import json
import os
from pathlib import Path

import pytest

from repo2ree_testbed.records import RunRecord, RunTest, read
from repo2ree_testbed.runs import inspect_run


def run_test(directory: str, rees: tuple[str, ...] = ()) -> RunTest:
    return RunTest(
        name=directory,
        selection=(),
        outcome="passed",
        reason="",
        exit_code=0,
        started=0,
        finished=1,
        rees=rees,
        phases={},
        directory=directory,
    )


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """The checker and traceview as asked to run; the checker finds a violation and writes its verification."""
    ran: list[tuple[str, ...]] = []

    def tool(log: Path, *args: str) -> int:
        ran.append(args)
        if args[1] == "check":
            verification = Path(args[args.index("-o") + 1])
            verification.mkdir(parents=True, exist_ok=True)
            (verification / "verification.json").write_text("{}")
            return 1
        return 0

    monkeypatch.setattr(inspect_run, "tool", tool)
    return ran


def dossier_at(directory: Path) -> Path:
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text("{}")
    return directory


def test_a_dossier_a_run_left_is_judged_in_place_and_its_test_row_updated(
    tmp_path: Path, tools: list[tuple[str, ...]]
) -> None:
    run = tmp_path / "e2e-system-1"
    judged, other = run_test("tests/judged", rees=("ree-1",)), run_test("tests/other")
    (run / "run.json").parent.mkdir(parents=True)
    (run / "run.json").write_text(
        RunRecord(tier="t", suite="s", build_revision="", jobs=1, tests=(judged, other)).model_dump_json()
    )
    dossier = dossier_at(run / "tests/judged/dossier")
    (run / "tests/judged/test.json").write_text("{}")

    assert inspect_run.inspect_dossier(dossier) == "violated"

    check, trace = tools
    assert check[check.index("-o") + 1] == str(run / "tests/judged/verification")
    assert trace[trace.index("-o") + 1] == str(run / "tests/judged/traces")
    record = read(RunRecord, run / "run.json")
    assert record is not None
    assert [test.behaviour for test in record.tests] == ["violated", None]
    assert (run / "index.html").is_file()
    assert (run / "tests/judged/index.html").is_file()


def test_a_failed_test_records_its_last_failed_command_beside_its_outcome(
    tmp_path: Path, tools: list[tuple[str, ...]]
) -> None:
    run = tmp_path / "e2e-gui-1"
    failed = run_test("tests/suite").but(outcome="failed", exit_code=1)
    (run / "tests/suite").mkdir(parents=True)
    (run / "run.json").write_text(
        RunRecord(tier="t", suite="s", build_revision="", jobs=1, tests=(failed,)).model_dump_json()
    )
    telemetry = dossier_at(run / "tests/suite/dossier") / "telemetry"
    telemetry.mkdir()
    attributes = {
        "repo2ree.exec.argv": "sh build.sh",
        "repo2ree.exit_code": 1,
        "repo2ree.exec.stderr_tail": "Temporary failure in name resolution\nERROR: failed to build\n",
    }
    (telemetry / "api.ndjson").write_text(
        json.dumps(
            {"name": "process.exec", "end_time": "t", "status": {"status_code": "ERROR"}, "attributes": attributes}
        )
    )

    inspect_run.inspect_run(run)

    record = read(RunRecord, run / "run.json")
    assert record is not None
    [test] = record.tests
    assert (
        test.last_failed_command
        == "`sh build.sh` exited 1: Temporary failure in name resolution … ERROR: failed to build"
    )
    page = (run / "tests/suite/index.html").read_text()
    assert "Last failed command" in page
    assert "ERROR: failed to build" in page
    assert "Temporary failure in name resolution" in (run / "index.html").read_text()


def test_a_dossier_collected_elsewhere_reports_under_the_assurance_directory(
    tmp_path: Path, tools: list[tuple[str, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REPO2REE_ASSURANCE_DIR", str(tmp_path / "assurance"))
    dossier = dossier_at(tmp_path / "collected")

    assert inspect_run.inspect_dossier(dossier) == "violated"

    check, trace = tools
    assert check[check.index("-o") + 1] == str(tmp_path / "assurance/verification/collected")
    assert trace[trace.index("-o") + 1] == str(tmp_path / "assurance/traces/collected")
    assert not (dossier / "verification").exists()


def test_the_newest_is_found_by_when_it_was_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inspect_run, "run_dir", lambda: tmp_path)
    with pytest.raises(ValueError, match="no dossier"):
        inspect_run.newest("*/tests/*/dossier/manifest.json", "dossier")
    older = dossier_at(tmp_path / "e2e/run-b/tests/t/dossier")
    newer = dossier_at(tmp_path / "e2e/run-a/tests/t/dossier")
    os.utime(older / "manifest.json", (1, 1))
    assert inspect_run.newest("*/tests/*/dossier/manifest.json", "dossier") == newer

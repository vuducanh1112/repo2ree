import json
import os
from pathlib import Path

import pytest

from repo2ree_testbed import provenance
from repo2ree_testbed.records import RunRecord, RunTest, read
from repo2ree_testbed.runs import assess, visualize


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

    monkeypatch.setattr(assess, "tool", tool)
    return ran


def dossier_at(directory: Path) -> Path:
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text("{}")
    return directory


def test_a_dossier_a_run_left_is_assessed_as_its_test_and_nothing_drawn(
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

    assert assess.assess_dossier(dossier) == "violated"

    [check] = tools
    assert check[check.index("-o") + 1] == str(run / "tests/judged/verification")
    assert not (run / "tests/judged/traces").exists()
    record = read(RunRecord, run / "run.json")
    assert record is not None
    assert [test.behaviour for test in record.tests] == ["violated", None]
    assert not (run / "index.html").exists()
    assert not (run / "tests/judged/index.html").exists()


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

    assess.assess_run(run)

    record = read(RunRecord, run / "run.json")
    assert record is not None
    [test] = record.tests
    assert (
        test.last_failed_command
        == "`sh build.sh` exited 1: Temporary failure in name resolution … ERROR: failed to build"
    )
    visualize.visualize_run(run)
    page = (run / "tests/suite/index.html").read_text()
    assert "Last failed command" in page
    assert "ERROR: failed to build" in page
    assert "Temporary failure in name resolution" in (run / "index.html").read_text()


def test_a_dossier_collected_elsewhere_is_assessed_under_the_assurance_directory(
    tmp_path: Path, tools: list[tuple[str, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REPO2REE_ASSURANCE_DIR", str(tmp_path / "assurance"))
    dossier = dossier_at(tmp_path / "collected")

    assert assess.assess_dossier(dossier) == "violated"

    [check] = tools
    assert check[check.index("-o") + 1] == str(tmp_path / "assurance/verification/collected")
    assert not (dossier / "verification").exists()


def test_a_path_names_a_run_or_a_dossier_and_none_the_newest_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(assess, "run_dir", lambda: tmp_path)
    with pytest.raises(ValueError, match="no per-test run"):
        assess.target("")
    for name, written in [("run-b", 1), ("run-a", 2)]:
        (tmp_path / "e2e" / name).mkdir(parents=True)
        (tmp_path / "e2e" / name / "run.json").write_text("{}")
        os.utime(tmp_path / "e2e" / name / "run.json", (written, written))
    assert assess.target("") == tmp_path / "e2e/run-a"
    dossier = dossier_at(tmp_path / "e2e/run-b/tests/t/dossier")
    assert assess.target(str(dossier)) == dossier
    assert assess.is_run(assess.target(str(tmp_path / "e2e/run-b")))
    with pytest.raises(ValueError, match="neither a run"):
        assess.target(str(tmp_path / "e2e/run-b/tests"))


def test_a_run_records_the_tree_that_assessed_it_and_an_invocation_assesses_its_runs(
    tmp_path: Path, tools: list[tuple[str, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(assess, "run_dir", lambda: tmp_path)
    monkeypatch.setattr(provenance, "clean_tree", lambda: "c" * 40)
    for name, invocation in [("e2e-system-1", "gate"), ("e2e-faults-1", "gate"), ("e2e-gui-1", "other")]:
        run = tmp_path / "e2e" / name
        dossier_at(run / "tests/t/dossier")
        (run / "run.json").write_text(
            RunRecord(
                tier=name, suite="s", build_revision="", jobs=1, invocation=invocation, tests=(run_test("tests/t"),)
            ).model_dump_json()
        )
    assert [run.name for run in assess.runs_of("gate")] == ["e2e-faults-1", "e2e-system-1"]
    monkeypatch.setattr("sys.argv", ["assess", "--invocation", "gate"])
    assert assess.main() == 0

    assessed = {name: read(RunRecord, tmp_path / "e2e" / name / "run.json") for name in ("e2e-system-1", "e2e-gui-1")}
    system, gui = assessed["e2e-system-1"], assessed["e2e-gui-1"]
    assert system is not None
    assert system.assessed_tree == "c" * 40
    assert gui is not None
    assert gui.assessed_tree == ""
    assert [test.behaviour for test in gui.tests] == [None]

    # One test assessed again from another tree leaves the run assessed by no single tree.
    monkeypatch.setattr(provenance, "clean_tree", lambda: "d" * 40)
    (tmp_path / "e2e/e2e-system-1/tests/t/test.json").write_text("{}")
    assess.assess_dossier(tmp_path / "e2e/e2e-system-1/tests/t/dossier")
    again = read(RunRecord, tmp_path / "e2e/e2e-system-1/run.json")
    assert again is not None
    assert again.assessed_tree == ""

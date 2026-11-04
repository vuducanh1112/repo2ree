"""Assessing runs and dossiers beside them, and visualizing what was assessed."""

import argparse
import json
import sys
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
def tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[tuple[str, ...]]:
    """The checker and traceview as asked to run, in an e2e run directory of the test's own: the checker
    finds a violation and writes its verification, traceview draws one page."""
    ran: list[tuple[str, ...]] = []

    def tool(log: Path, *args: str) -> int:
        ran.append(args)
        out = Path(args[args.index("-o") + 1])
        out.mkdir(parents=True, exist_ok=True)
        if args[1] == "check":
            (out / "verification.json").write_text("{}")
            return 1
        (out / "ree-1.html").write_text("<html></html>")
        return 0

    monkeypatch.setattr(assess, "tool", tool)
    monkeypatch.setattr(visualize, "tool", tool)
    monkeypatch.setattr(assess, "run_dir", lambda: tmp_path)
    monkeypatch.setattr(provenance, "clean_tree", lambda: "c" * 40)
    monkeypatch.setattr(provenance, "clean_revision", lambda: "a" * 40)
    return ran


def dossier_at(directory: Path) -> Path:
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text("{}")
    return directory


def a_run(tmp_path: Path, name: str, *tests: RunTest, invocation: str = "") -> Path:
    run = tmp_path / "e2e" / name
    for test in tests:
        dossier_at(run / test.directory / "dossier")
        (run / test.directory / "test.json").write_text("{}")
    record = RunRecord(tier=name, suite="s", build_revision="", jobs=1, invocation=invocation, tests=tests)
    (run / "run.json").write_text(record.model_dump_json())
    return run


def files(directory: Path) -> list[Path]:
    return sorted(path.relative_to(directory) for path in directory.rglob("*"))


def test_a_run_is_assessed_beside_itself_and_left_as_it_was(tmp_path: Path, tools: list[tuple[str, ...]]) -> None:
    run, reports = a_run(tmp_path, "e2e-system-1", run_test("tests/t", rees=("r",))), tmp_path / "reports"
    before = files(run)

    assess.assess_run(run, reports)

    assert files(run) == before
    [check] = tools
    assert check[check.index("--dossier") + 1] == str(run / "tests/t/dossier")
    assert check[check.index("-o") + 1] == str(reports / "e2e-system-1/tests/t/verification")
    report = read(RunRecord, reports / "e2e-system-1/run.json")
    assert report is not None
    assert [test.behaviour for test in report.tests] == ["violated"]
    assert (report.assessed_tree, report.assessed_revision) == ("c" * 40, "a" * 40)


def test_a_failed_test_records_its_last_failed_command_beside_its_outcome(
    tmp_path: Path, tools: list[tuple[str, ...]]
) -> None:
    run = a_run(tmp_path, "e2e-gui-1", run_test("tests/suite").but(outcome="failed", exit_code=1))
    telemetry = run / "tests/suite/dossier/telemetry"
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
    reports = tmp_path / "reports"

    assess.assess_run(run, reports)

    report = read(RunRecord, reports / "e2e-gui-1/run.json")
    assert report is not None
    [test] = report.tests
    assert (
        test.last_failed_command
        == "`sh build.sh` exited 1: Temporary failure in name resolution … ERROR: failed to build"
    )
    visualize.visualize_run(run, reports)
    page = (reports / "e2e-gui-1/tests/suite/index.html").read_text()
    assert "ERROR: failed to build" in page
    assert "Temporary failure in name resolution" in (reports / "e2e-gui-1/index.html").read_text()


def test_one_dossier_of_a_run_is_assessed_as_its_test_in_the_runs_report(
    tmp_path: Path, tools: list[tuple[str, ...]]
) -> None:
    run = a_run(tmp_path, "e2e-system-1", run_test("tests/judged"), run_test("tests/other"))
    reports = tmp_path / "reports"
    assert assess.assess_dossier(run / "tests/judged/dossier", reports) == "violated"
    report = read(RunRecord, reports / "e2e-system-1/run.json")
    assert report is not None
    assert [test.behaviour for test in report.tests] == ["violated", None]
    # Not a whole run assessed by one tree.
    assert report.assessed_tree == ""


def test_a_dossier_collected_elsewhere_is_assessed_under_collected(
    tmp_path: Path, tools: list[tuple[str, ...]]
) -> None:
    dossier, reports = dossier_at(tmp_path / "staging-demo"), tmp_path / "reports"
    assert assess.assess_dossier(dossier, reports) == "violated"
    [check] = tools
    assert check[check.index("-o") + 1] == str(reports / "collected/staging-demo/verification")
    assert files(dossier) == [Path("manifest.json")]


def test_what_to_assess_is_named_by_path_or_run_name_and_is_the_receipts_runs_by_default(
    tmp_path: Path, tools: list[tuple[str, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    system = a_run(tmp_path, "e2e-system-1", run_test("tests/t"), invocation="gate")
    faults = a_run(tmp_path, "e2e-faults-1", run_test("tests/t"), invocation="gate")
    a_run(tmp_path, "e2e-gui-1", run_test("tests/t"), invocation="other")
    monkeypatch.setattr(assess, "receipt_runs", lambda: {system.resolve()})

    def chosen(*argv: str) -> list[str]:
        parser = argparse.ArgumentParser()
        assess.choosing(parser, "assess")
        return [path.name for path in assess.chosen(parser.parse_args(argv))]

    assert chosen() == ["e2e-system-1"]
    assert chosen("e2e-faults-1", str(system / "tests/t/dossier")) == ["e2e-faults-1", "dossier"]
    assert chosen("--invocation", "gate") == ["e2e-faults-1", "e2e-system-1"]
    with pytest.raises(ValueError, match="neither a run"):
        chosen(str(faults / "tests"))


def test_reports_of_runs_gone_from_disk_go_and_collected_ones_stay(
    tmp_path: Path, tools: list[tuple[str, ...]]
) -> None:
    kept, reports = a_run(tmp_path, "e2e-system-1", run_test("tests/t")), tmp_path / "reports"
    for name in ("e2e-system-1", "e2e-system-0", "collected", "elsewhere"):
        (reports / name).mkdir(parents=True)
    assess.drop_gone(reports, frozenset({"elsewhere"}))
    assert sorted(path.name for path in reports.iterdir()) == ["collected", "e2e-system-1", "elsewhere"]
    assert kept.is_dir()


def test_assessing_exits_zero_whatever_the_verdict(
    tmp_path: Path, tools: list[tuple[str, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    dossier = dossier_at(tmp_path / "staging-demo")
    monkeypatch.setattr(sys, "argv", ["assess", "--reports", str(tmp_path / "reports"), str(dossier)])
    assert assess.main() == 0


def test_a_runs_report_has_its_tests_traces_drawn_and_its_evidence_linked_from_the_run(
    tmp_path: Path, tools: list[tuple[str, ...]]
) -> None:
    run = a_run(tmp_path, "e2e-system-1", run_test("tests/drawn", rees=("ree-1",)), run_test("tests/no-ree"))
    (run / "tests/drawn/logs").mkdir()
    (run / "tests/drawn/logs/api.log").write_text("x")
    reports = tmp_path / "reports"
    assess.assess_run(run, reports)
    before = files(run)

    visualize.visualize_run(run, reports)

    assert files(run) == before
    trace = next(args for args in tools if args[1] == "trace")
    assert trace[trace.index("-o") + 1] == str(reports / "e2e-system-1/tests/drawn/traces")
    assert trace[trace.index("--dossier") + 1] == str(run / "tests/drawn/dossier")
    page = (reports / "e2e-system-1/tests/drawn/index.html").read_text()
    assert "href='traces/ree-1.html'" in page
    assert "href='../../../../e2e/e2e-system-1/tests/drawn/logs/api.log'" in page
    assert (reports / "e2e-system-1/index.html").is_file()


def test_a_run_not_assessed_yet_is_not_drawn(tmp_path: Path, tools: list[tuple[str, ...]]) -> None:
    run = a_run(tmp_path, "e2e-system-1", run_test("tests/t"))
    with pytest.raises(ValueError, match="not assessed yet"):
        visualize.visualize_run(run, tmp_path / "reports")


def test_a_collected_dossier_is_drawn_beside_its_assessment(tmp_path: Path, tools: list[tuple[str, ...]]) -> None:
    dossier, reports = dossier_at(tmp_path / "staging-demo"), tmp_path / "reports"
    with pytest.raises(ValueError, match="not assessed yet"):
        visualize.visualize_dossier(dossier, reports)
    assess.assess_dossier(dossier, reports)
    visualize.visualize_dossier(dossier, reports)
    trace = next(args for args in tools if args[1] == "trace")
    assert trace[trace.index("-o") + 1] == str(reports / "collected/staging-demo/traces")

"""The gated tests judged and drawn again by this tree, and the gate page saying where that differs."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo2ree_repoview.overview import gate_reports
from repo2ree_repoview.overview.pages.gates import judged_now
from repo2ree_repoview.overview.receipt import GateReport, GateReports, ReceiptTest, RunTest


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """The checker and traceview as asked to run: the checker finds a violation, traceview draws."""
    ran: list[tuple[str, ...]] = []

    def tool(*args: str) -> subprocess.CompletedProcess[str]:
        ran.append(args)
        return subprocess.CompletedProcess(args, 1 if args[1] == "check" else 0, "", "")

    monkeypatch.setattr(gate_reports, "tool", tool)
    return ran


def dossier_of(run: Path, directory: str) -> None:
    (run / directory / "dossier").mkdir(parents=True)
    (run / directory / "dossier/manifest.json").write_text("{}")


def test_a_test_is_checked_and_its_traces_drawn_beside_the_run_not_in_it(
    tmp_path: Path, tools: list[tuple[str, ...]]
) -> None:
    run, reports = tmp_path / "e2e-system-1", tmp_path / "reports"
    dossier_of(run, "tests/t")
    found = gate_reports.report(run, RunTest(name="t", directory="tests/t", rees=("r",)), reports)
    assert found == GateReport(run="e2e-system-1", test="t", behaviour="violated")
    check, trace = tools
    assert check[check.index("-o") + 1] == str(reports / "e2e-system-1/tests/t/verification")
    assert trace[trace.index("-o") + 1] == str(reports / "e2e-system-1/tests/t/traces")
    assert trace[trace.index("--dossier") + 1] == str(run / "tests/t/dossier")


def test_a_test_without_rees_is_only_checked_and_one_without_a_dossier_is_missing(
    tmp_path: Path, tools: list[tuple[str, ...]]
) -> None:
    run = tmp_path / "run"
    dossier_of(run, "tests/t")
    assert gate_reports.report(run, RunTest(name="t", directory="tests/t"), tmp_path).behaviour == "violated"
    assert [args[1] for args in tools] == ["check"]
    missing = gate_reports.report(run, RunTest(name="u", directory="tests/u"), tmp_path)
    assert (missing.behaviour, missing.problem) == ("missing", "no dossier")


def test_a_checker_that_fails_gives_no_verdict_and_says_why(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    crashed = subprocess.CompletedProcess((), 3, "", "Traceback ...\nValueError: unknown journal format\n")
    monkeypatch.setattr(gate_reports, "tool", lambda *args: crashed)
    run = tmp_path / "run"
    dossier_of(run, "tests/t")
    found = gate_reports.report(run, RunTest(name="t", directory="tests/t", rees=("r",)), tmp_path)
    assert (found.behaviour, found.problem) == ("error", "ValueError: unknown journal format")


def test_reports_replace_only_earlier_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere/notes.txt").write_text("mine")
    monkeypatch.setattr("sys.argv", ["gate-reports", "-o", str(tmp_path / "elsewhere")])
    with pytest.raises(SystemExit):
        gate_reports.main()
    assert (tmp_path / "elsewhere/notes.txt").is_file()


def test_the_gate_page_says_where_this_trees_checker_judges_differently() -> None:
    certified = ReceiptTest(run="r", test="t", outcome="passed", behaviour="passed")
    reports = GateReports(
        format="repo2ree-gate-reports/1", tests=(GateReport(run="r", test="t", behaviour="violated", problem=None),)
    )
    assert '<span class="no">violated</span>' in judged_now(certified, reports)
    agreeing = GateReports(format="repo2ree-gate-reports/1", tests=(GateReport(run="r", test="t", behaviour="passed"),))
    assert "agrees" in judged_now(certified, agreeing)
    assert "just report-assurance-gate" in judged_now(certified, None)

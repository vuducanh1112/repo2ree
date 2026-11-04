"""Assess the behaviour of e2e runs' tests, or of one dossier: check each dossier against the
behaviour specification and record the verdict, beside what it assesses. A run only collects and
is never written: its assessment is a report of it, laid out like it, under reports/behaviour/:
<run>/run.json with each test's verdict, its last failed command, and the clean tree and commit
that assessed them, and <run>/<test>/verification/. ``repo2ree_testbed visualize`` draws them.

What to assess: runs, by path or by name; a dossier one of their tests left, which is assessed as
that test; a dossier collected from a live deployment (``collect-dossier``), reported under
collected/<name>/; every run of an invocation (``--invocation``, as the assurance gate assesses
its tiers); and, by default, the runs the assurance-gate receipt names. Reports whose run is gone
go too.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from repo2ree_testbed import provenance
from repo2ree_testbed.artifacts import ROOT, run_dir
from repo2ree_testbed.records import Behaviour, RunRecord, RunTest, read, write
from repo2ree_testbed.runs.failed_command import FailedCommand, last_failed_command
from repo2ree_testbed.runs.prune import receipt_runs

REPORTS = ROOT / "reports" / "behaviour"
COLLECTED = "collected"
VERDICTS: dict[int, Behaviour] = {0: "passed", 1: "violated", 2: "inconclusive"}


def tool(log: Path, *args: str) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as output:
        command = [sys.executable, "-m", *args]
        return subprocess.run(command, cwd=ROOT, check=False, stdout=output, stderr=subprocess.STDOUT).returncode


def judge(dossier: Path, verification: Path, logs: Path) -> Behaviour:
    """Check a dossier into ``verification``."""
    if not (dossier / "manifest.json").is_file():
        return "missing"
    check = ("repo2ree_assurance_checker", "check", "--dossier", str(dossier), "-o", str(verification))
    return VERDICTS.get(tool(logs / "checker.log", *check), "error")


def failed_command(directory: Path, test: RunTest) -> FailedCommand | None:
    """The last workbench command a failed test's dossier records as failing."""
    return last_failed_command(directory / "dossier" / "telemetry") if test.outcome == "failed" else None


def assess_test(evidence: Path, test: RunTest, report: Path) -> RunTest:
    """Assess the test whose evidence is in ``evidence``, its verification and logs going into ``report``."""
    assessed = test.judged(judge(evidence / "dossier", report / "verification", report / "logs"))
    failed = failed_command(evidence, test)
    return assessed if failed is None else assessed.but(last_failed_command=failed.summary())


def assessed_by() -> dict[str, str]:
    return {"assessed_tree": provenance.clean_tree(), "assessed_revision": provenance.clean_revision()}


def assess_run(run: Path, reports: Path = REPORTS) -> RunRecord:
    record = read(RunRecord, run / "run.json")
    if record is None:
        raise ValueError(f"{run}: no run record (run.json) to assess")
    report = reports / run.name
    shutil.rmtree(report, ignore_errors=True)
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
        tests = list(
            pool.map(lambda test: assess_test(run / test.directory, test, report / test.directory), record.tests)
        )
    for test in tests:
        print(f"   {test.outcome:<7} behaviour {test.behaviour or '':<12} {test.name}")
        if test.last_failed_command:
            print(f"           outcome {test.outcome}, last failed command: {test.last_failed_command}")
    assessed = record.with_tests(tuple(tests)).but(**assessed_by())
    report.mkdir(parents=True, exist_ok=True)
    write(report / "run.json", assessed)
    print(f">> assessed {run.name}: {report / 'run.json'}")
    return assessed


def run_of(dossier: Path) -> tuple[Path, RunRecord] | None:
    """The run a dossier's test left it in, with its record; None for one collected elsewhere."""
    directory = dossier.parent
    root = directory.parent.parent
    run = read(RunRecord, root / "run.json") if (directory / "test.json").is_file() else None
    return None if run is None else (root, run)


def assess_dossier(dossier: Path, reports: Path = REPORTS) -> Behaviour:
    """Assess one dossier: as its test in its run's report, or under collected/ when no run left it."""
    found = run_of(dossier)
    if found is None:
        report = reports / COLLECTED / dossier.name
        verdict = judge(dossier, report / "verification", report / "logs")
        print(f">> {verdict}: {report / 'verification' / 'assurance.html'}")
        return verdict
    run, record = found
    name = str(dossier.parent.relative_to(run))
    report = reports / run.name
    # The run's report as it stands, or the run itself when it has none yet: only this test is assessed.
    current = read(RunRecord, report / "run.json") or record.but(assessed_tree="", assessed_revision="")
    tests = tuple(
        assess_test(dossier.parent, test, report / test.directory) if test.directory == name else test
        for test in current.tests
    )
    # One test assessed again keeps the report's tree only if it was assessed by that same tree.
    same = current.assessed_tree and current.assessed_tree == provenance.clean_tree()
    report.mkdir(parents=True, exist_ok=True)
    write(
        report / "run.json",
        current.with_tests(tests).but(**(assessed_by() if same else {"assessed_tree": "", "assessed_revision": ""})),
    )
    [assessed] = [test for test in tests if test.directory == name]
    print(f">> {assessed.behaviour}: {report / name / 'verification'}")
    return assessed.behaviour or "missing"


def drop_gone(reports: Path = REPORTS, keep: frozenset[str] = frozenset()) -> None:
    """Remove the reports of runs no longer on disk, but those of ``keep``, just assessed."""
    for report in sorted(reports.iterdir()) if reports.is_dir() else ():
        gone = not is_run(run_dir() / "e2e" / report.name)
        if report.name not in {COLLECTED, *keep} and report.is_dir() and gone:
            shutil.rmtree(report)


def runs_of(invocation: str) -> list[Path]:
    """The runs whose run.json names this invocation."""
    found = [
        record.parent
        for record in sorted((run_dir() / "e2e").glob("*/run.json"))
        if (run := read(RunRecord, record)) is not None and run.invocation == invocation
    ]
    if not found:
        raise ValueError(f"no run under {run_dir() / 'e2e'} names invocation {invocation}")
    return found


def gate_runs() -> list[Path]:
    """The runs the assurance-gate receipt names that are still on disk."""
    return sorted(run for run in receipt_runs() if is_run(run))


def is_run(path: Path) -> bool:
    return (path / "run.json").is_file()


def target(given: str) -> Path:
    """A run or a dossier, by path; a run also by its name, without a slash, under the e2e run directory."""
    chosen = (Path(given) if "/" in given else run_dir() / "e2e" / given).resolve()
    if is_run(chosen) or (chosen / "manifest.json").is_file():
        return chosen
    raise ValueError(f"{chosen}: neither a run (no run.json) nor a dossier (no manifest.json)")


def choosing(parser: argparse.ArgumentParser, verb: str) -> None:
    """What a command works on: runs or dossiers, an invocation's runs, or the receipt's runs by default."""
    parser.add_argument("targets", nargs="*", help="runs, by path or name, or dossiers (default: the receipt's runs)")
    parser.add_argument("--invocation", help=f"{verb} every run that names this invocation (REPO2REE_TEST_RUN_ID)")
    parser.add_argument("--reports", type=Path, default=REPORTS, help="where the reports are (default: %(default)s)")


def chosen(args: argparse.Namespace) -> list[Path]:
    """The runs and dossiers asked for."""
    if args.invocation:
        return [*runs_of(args.invocation), *(target(given) for given in args.targets)]
    return [target(given) for given in args.targets] if args.targets else gate_runs()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    choosing(parser, "assess")
    args = parser.parse_args()
    try:
        paths = chosen(args)
        for path in paths:
            if is_run(path):
                assess_run(path, args.reports)
            else:
                assess_dossier(path, args.reports)
        drop_gone(args.reports, frozenset(path.name for path in paths if is_run(path)))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Assess the behaviour of an e2e run's tests, or of one dossier: check each dossier against the
behaviour specification and record the verdict. Never changes a test's outcome, and draws nothing:
``repo2ree_testbed visualize`` draws what this records.

A run is a folder with a run.json, as ``repo2ree_testbed e2e --per-test`` writes it: every test's
dossier is checked into its verification/, and its verdict and last failed command recorded in
run.json. A dossier is a folder with a manifest.json: one a run's test left is assessed as that
test; one collected from a live deployment (``collect-dossier``) has its verification and logs
written under the assurance directory, by its name.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from repo2ree_testbed.artifacts import ROOT, domain_dir, run_dir
from repo2ree_testbed.records import Behaviour, RunRecord, RunTest, read, write
from repo2ree_testbed.runs.failed_command import FailedCommand, last_failed_command

VERDICTS: dict[int, Behaviour] = {0: "passed", 1: "violated", 2: "inconclusive"}
EXIT_CODES = {behaviour: code for code, behaviour in VERDICTS.items()}


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


def assess_test(directory: Path, test: RunTest) -> RunTest:
    assessed = test.judged(judge(directory / "dossier", directory / "verification", directory / "logs"))
    failed = failed_command(directory, test)
    return assessed if failed is None else assessed.but(last_failed_command=failed.summary())


def assess_run(root: Path) -> RunRecord:
    run = read(RunRecord, root / "run.json")
    if run is None:
        raise ValueError(f"{root}: no run record (run.json) to assess")
    tests = []
    for test in run.tests:
        assessed = assess_test(root / test.directory, test)
        tests.append(assessed)
        print(f"   {assessed.outcome:<7} behaviour {assessed.behaviour or '':<12} {test.name}")
        if assessed.last_failed_command:
            print(f"           outcome {assessed.outcome}, last failed command: {assessed.last_failed_command}")
    assessed_run = run.with_tests(tuple(tests))
    write(root / "run.json", assessed_run)
    print(f">> assessed: {root / 'run.json'}")
    print(f">> draw it: just visualize-behaviour {root}")
    return assessed_run


def run_of(dossier: Path) -> tuple[Path, RunRecord] | None:
    """The run a dossier's test left it in, with its record; None for one collected elsewhere."""
    directory = dossier.parent
    root = directory.parent.parent
    run = read(RunRecord, root / "run.json") if (directory / "test.json").is_file() else None
    return None if run is None else (root, run)


def assess_dossier(dossier: Path) -> Behaviour:
    """Assess one dossier: as its test, if a run's test left it, else under the assurance directory."""
    found = run_of(dossier)
    if found is not None:
        root, run = found
        name = str(dossier.parent.relative_to(root))
        tests = tuple(assess_test(dossier.parent, test) if test.directory == name else test for test in run.tests)
        write(root / "run.json", run.with_tests(tests))
        [assessed] = [test for test in tests if test.directory == name]
        print(f">> {assessed.behaviour}: {dossier.parent / 'verification'}")
        return assessed.behaviour or "missing"
    reports = domain_dir("assurance")
    verdict = judge(dossier, reports / "verification" / dossier.name, reports / "logs" / dossier.name)
    print(f">> {verdict}: {reports / 'verification' / dossier.name / 'assurance.html'}")
    return verdict


def newest_run() -> Path:
    found = sorted((run_dir() / "e2e").glob("*/run.json"), key=lambda path: path.stat().st_mtime)
    if not found:
        raise ValueError(f"no per-test run under {run_dir() / 'e2e'}; run an e2e tier first")
    return found[-1].parent


def target(path: str) -> Path:
    """A run (a folder with run.json) or a dossier (one with manifest.json); the newest run when not given."""
    chosen = Path(path).resolve() if path else newest_run()
    if (chosen / "run.json").is_file() or (chosen / "manifest.json").is_file():
        return chosen
    raise ValueError(f"{chosen}: neither a run (no run.json) nor a dossier (no manifest.json)")


def is_run(path: Path) -> bool:
    return (path / "run.json").is_file()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    # A string, not a path: a recipe passes "" for "the newest", and Path("") would be the working directory.
    parser.add_argument(
        "path",
        nargs="?",
        default="",
        help="a run or a dossier (default: the newest run); a dossier exits with "
        "its verdict: 0 passed, 1 violated, 2 inconclusive",
    )
    args = parser.parse_args()
    try:
        chosen = target(args.path)
        if not is_run(chosen):
            return EXIT_CODES.get(assess_dossier(chosen), 2)
        assess_run(chosen)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

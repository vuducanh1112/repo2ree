"""Judge and draw the assurance-gate receipt's tests again with this tree (``just report-assurance-gate``).

The receipt's runs keep what they left; this checks each test's dossier with the checker in this
tree and draws its traces with this tree's traceview, under reports/assurance/<run>/<test>/, and
writes reports/assurance/reports.json: each test's verdict now, or why it has none. It runs the
tools as their owners publish them, so the views never import the checker or traceview, and
replaces whatever an earlier report left.

    python -m repo2ree_repoview gate-reports -o reports/assurance
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from repo2ree_repoview.overview.receipt import (
    REPORTS,
    GateReport,
    GateReports,
    RunTest,
    gate_runs,
    read_receipt,
    reported,
)
from repo2ree_repoview.repository import ROOT

VERDICTS = {0: "passed", 1: "violated", 2: "inconclusive"}


def tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=False, capture_output=True, text=True)


def failure(ran: subprocess.CompletedProcess[str]) -> str:
    lines = (ran.stderr or ran.stdout).strip().splitlines()
    return lines[-1] if lines else f"exit {ran.returncode}"


def report(run: Path, test: RunTest, reports: Path) -> GateReport:
    """Check one test's dossier and draw its traces; its verdict, or why there is none."""
    dossier = run / test.directory / "dossier"
    if not (dossier / "manifest.json").is_file():
        return GateReport(run=run.name, test=test.name, behaviour="missing", problem="no dossier")
    target = reported(run, test, reports)
    checked = tool("repo2ree_assurance_checker", "check", "--dossier", str(dossier), "-o", str(target / "verification"))
    behaviour = VERDICTS.get(checked.returncode)
    if behaviour is None:
        return GateReport(run=run.name, test=test.name, behaviour="error", problem=failure(checked))
    if not test.rees:
        return GateReport(run=run.name, test=test.name, behaviour=behaviour)
    traces = ("trace", str(target / "verification"), "--dossier", str(dossier), "-o", str(target / "traces"))
    drawn = tool("repo2ree_assurance_traceview", *traces, "--provenance")
    problem = None if drawn.returncode == 0 else f"traces not drawn: {failure(drawn)}"
    return GateReport(run=run.name, test=test.name, behaviour=behaviour, problem=problem)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", type=Path, default=REPORTS, help="where the reports go")
    args = parser.parse_args()
    output: Path = args.output
    if output.is_dir() and any(output.iterdir()) and not (output / "reports.json").is_file():
        parser.exit(1, f"{output} holds something other than gate reports; refusing to replace it\n")
    shutil.rmtree(output, ignore_errors=True)
    tests = [(run, test) for run, record in gate_runs(read_receipt()) for test in record.tests]
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
        reports = list(pool.map(lambda pair: report(pair[0], pair[1], output), tests))
    output.mkdir(parents=True, exist_ok=True)
    summary = GateReports(format="repo2ree-gate-reports/1", tests=tuple(reports))
    (output / "reports.json").write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for item in reports:
        print(f"   {item.behaviour:<12} {item.test}" + (f"  ({item.problem})" if item.problem else ""))
    print(f">> {len(reports)} gated tests reported on under {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

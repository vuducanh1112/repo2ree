"""``python -m repo2ree_testbed record --tier T -- COMMAND...``: a run record for a tier that is not an e2e run.

The e2e tiers write their own run records. Backend integration and the GUI's
accessibility and screenshot suites are plain pytest and Playwright runs, so this
wraps one: it gives the command a directory for JUnit reports
(``REPO2REE_JUNIT_DIR``, and ``PLAYWRIGHT_JUNIT_OUTPUT_FILE`` for Playwright's
reporter), runs it, and writes ``test-artifacts/e2e/<tier>-<time>/run.json`` from
the reports: the same record, with the same tree, platform, and machine, that a
gate's certifier reads (``scripts/gates/tiers.py``). The command's exit code is
this command's.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from xml.etree import ElementTree

from repo2ree_testbed import provenance
from repo2ree_testbed.artifacts import ROOT, execution_id, run_dir
from repo2ree_testbed.records import Outcome, RunRecord, RunTest, write
from repo2ree_testbed.stack.process import capture


def outcomes(directory: Path, started: float, finished: float) -> list[RunTest]:
    """Every test case in the JUnit reports under ``directory``."""
    tests = []
    for report in sorted(directory.glob("*.xml")):
        root = ElementTree.parse(report).getroot()  # noqa: S314 - a report this run's own test runner wrote
        for case in root.iter("testcase"):
            outcome: Outcome = "passed"
            reason = ""
            for child in case:
                if child.tag in {"failure", "error"}:
                    outcome, reason = "failed", child.get("message", "")
                elif child.tag == "skipped":
                    outcome, reason = "skipped", child.get("message", "")
            name = "::".join(part for part in (case.get("classname", ""), case.get("name", "")) if part)
            tests.append(
                RunTest(
                    name=name,
                    selection=(),
                    outcome=outcome,
                    reason=reason,
                    exit_code=0 if outcome != "failed" else 1,
                    started=started,
                    finished=finished,
                    rees=(),
                    phases={},
                    directory=".",
                )
            )
    return tests


def record(tier: str, command: list[str]) -> int:
    root = run_dir() / "e2e" / f"{tier}-{time.strftime('%Y%m%d-%H%M%S')}"
    reports = root / "junit"
    reports.mkdir(parents=True, exist_ok=True)
    revision = os.environ.get("REPO2REE_BUILD_REVISION") or capture([str(ROOT / "scripts/build-revision.sh")])
    tree = provenance.clean_tree()
    environment = {
        **os.environ,
        "REPO2REE_JUNIT_DIR": str(reports),
        "PLAYWRIGHT_JUNIT_OUTPUT_FILE": str(reports / "playwright.xml"),
    }
    started = time.time()
    status = subprocess.run(command, cwd=ROOT, env=environment, check=False).returncode
    finished = time.time()
    tests = outcomes(reports, started, finished)
    write(
        root / "run.json",
        RunRecord(
            tier=tier,
            suite=tier,
            build_revision=revision,
            jobs=1,
            whole_suite=True,
            invocation=execution_id(),
            tree=tree if tree and provenance.clean_tree() == tree else "",
            platform=provenance.platform(),
            machine=provenance.machine(),
            tests=tuple(tests),
        ),
    )
    counts = {outcome: sum(test.outcome == outcome for test in tests) for outcome in ("passed", "failed", "skipped")}
    print(f">> {tier}: {counts['passed']} passed, {counts['failed']} failed, {counts['skipped']} skipped -> {root}")
    if status == 0 and not tests:
        print(f">> {tier} wrote no JUnit report; its run record names no test", file=sys.stderr)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed record", description=__doc__.split("\n\n")[0])
    parser.add_argument("--tier", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("record needs a command after --")
    return record(args.tier, command)


if __name__ == "__main__":
    raise SystemExit(main())

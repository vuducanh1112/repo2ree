#!/usr/bin/env python3
"""Judge per-test e2e runs on their behaviour, and certify the tree they ran on.

Test runs only collect; inspect_run.py draws verdicts but never fails a run. This
composes the two into a gate:

- ``judge RUN...`` checks every test's recording again with the checker in this
  tree and accepts a test only if it passed and its behaviour passed, or the
  test ``conformance/expected-verdicts.toml`` excuses (an xfail must be) left
  exactly the rules it names non-passing. Exit 1 if any test is not accepted.
- ``certify RUN...`` judges, then also requires every tier in ``TIERS`` to be among
  the runs, each built from HEAD with a clean tree that is still HEAD, and every
  expectation to have been used. It writes ``.validation-certificates/behaviour-ok``,
  binding the verdicts to HEAD's tree.
- ``verify`` requires that receipt to cover HEAD's tree, and the tree to be clean.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXPECTATIONS = ROOT / "conformance/expected-verdicts.toml"
RECEIPT = ROOT / ".validation-certificates/behaviour-ok"
# The per-test tiers whose evidence a receipt stands on.
TIERS = ("e2e-system", "e2e-gui-instant")
ACCEPTED_OUTCOMES = {"passed", "xfailed"}
NON_PASSING = ("violated", "inconclusive")


@dataclass(frozen=True)
class Expectation:
    test: str
    violated: frozenset[str]
    inconclusive: frozenset[str]
    reason: str


@dataclass
class Judgement:
    run: str
    test: str
    outcome: str
    behaviour: str
    rules: dict[str, frozenset[str]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    excused_by: str = ""

    @property
    def accepted(self) -> bool:
        return not self.problems


def load_expectations(path: Path = EXPECTATIONS) -> dict[str, Expectation]:
    entries = tomllib.loads(path.read_text()).get("expected", [])
    expectations: dict[str, Expectation] = {}
    for entry in entries:
        unknown = set(entry) - {"test", "violated", "inconclusive", "reason"}
        if unknown or not entry.get("test") or not str(entry.get("reason", "")).strip():
            raise ValueError(f"{path}: an expectation needs a test and a reason, and nothing else: {entry}")
        if entry["test"] in expectations:
            raise ValueError(f"{path}: {entry['test']} is expected twice")
        expectations[entry["test"]] = Expectation(
            entry["test"],
            frozenset(entry.get("violated", [])),
            frozenset(entry.get("inconclusive", [])),
            entry["reason"],
        )
    return expectations


def check_recording(directory: Path) -> dict[str, Any] | None:
    """The checker's report on a test's recording, from the checker in this tree; None without a recording."""
    recording = directory / "recording"
    if not (recording / "manifest.json").is_file():
        return None
    output = directory / "verification"
    command = [sys.executable, "-m", "repo2ree_conformance", "check", "--recording", str(recording), "-o", str(output)]
    if subprocess.run(command, cwd=ROOT, check=False, capture_output=True).returncode not in {0, 1, 2}:
        return None
    report: dict[str, Any] = json.loads((output / "conformance.json").read_text())
    return report


def judge_test(run: str, directory: Path, test: dict[str, Any], expectations: dict[str, Expectation]) -> Judgement:
    name = str(test["name"])
    judgement = Judgement(run, name, str(test["outcome"]), "missing")
    if judgement.outcome not in ACCEPTED_OUTCOMES:
        judgement.problems.append(f"test {judgement.outcome}")
    report = check_recording(directory)
    if report is None:
        judgement.problems.append("no behaviour verdict: the recording is missing or the checker failed")
        return judgement
    judgement.behaviour = str(report["verdict"])
    judgement.rules = {
        verdict: frozenset(rule["rule"] for rule in report["rules"] if rule["verdict"] == verdict)
        for verdict in NON_PASSING
    }
    expected = expectations.get(name)
    if expected is None:
        # Tests are not oracle: marking a failing test xfail must not be enough to pass the gate.
        if judgement.outcome == "xfailed":
            judgement.problems.append("xfailed, and expected-verdicts.toml does not excuse it")
        if judgement.behaviour != "passed":
            judgement.problems.append(f"behaviour {judgement.behaviour}: {describe(judgement.rules)}")
        return judgement
    wanted = {"violated": expected.violated, "inconclusive": expected.inconclusive}
    if judgement.rules != wanted:
        judgement.problems.append(
            f"behaviour {judgement.behaviour}: {describe(judgement.rules)}; expected-verdicts.toml excuses "
            f"{describe(wanted)}"
        )
    else:
        judgement.excused_by = expected.reason
    return judgement


def describe(rules: dict[str, frozenset[str]]) -> str:
    parts = [f"{verdict} {', '.join(sorted(names))}" for verdict, names in rules.items() if names]
    return "; ".join(parts) or "no rule open"


def judge_runs(runs: list[Path], expectations: dict[str, Expectation]) -> list[Judgement]:
    return [
        judge_test(root.name, root / test["directory"], test, expectations)
        for root in runs
        for test in json.loads((root / "run.json").read_text())["tests"]
    ]


def report(judgements: list[Judgement], problems: list[str]) -> None:
    for item in judgements:
        mark = "ok  " if item.accepted else "FAIL"
        excused = "  (excused)" if item.excused_by else ""
        print(f"{mark} {item.outcome:<8} behaviour {item.behaviour:<13} {item.test}{excused}")
        for problem in item.problems:
            print(f"       {problem}")
    for problem in problems:
        print(f"FAIL {problem}")
    accepted = sum(item.accepted for item in judgements)
    print(f">> behaviour gate: {accepted}/{len(judgements)} tests accepted, {len(problems)} other problems")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def clean_head() -> tuple[str, str, list[str]]:
    """(HEAD's commit, its tree, problems): a dirty tree is a problem, since the receipt names HEAD."""
    problems = ["the working tree is not clean; commit first"] if git("status", "--porcelain") else []
    return git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}"), problems


def certification_problems(
    runs: list[Path], judgements: list[Judgement], expectations: dict[str, Expectation]
) -> list[str]:
    revision, _, problems = clean_head()
    tiers: dict[str, Path] = {}
    for root in runs:
        run = json.loads((root / "run.json").read_text())
        built = run.get("build_revision") or "an unknown build"
        if built != revision:
            problems.append(f"{root.name} ran on {built}, not HEAD {revision}")
        if run["tier"] in tiers:
            problems.append(f"{root.name} and {tiers[run['tier']].name} are both {run['tier']} runs")
        tiers[run["tier"]] = root
    problems += [f"no {tier} run among the runs certified" for tier in TIERS if tier not in tiers]
    seen = {item.test for item in judgements}
    unused = [name for name in expectations if name not in seen]
    problems += [f"expected-verdicts.toml excuses {name}, which no run ran" for name in unused]
    return problems


def write_receipt(judgements: list[Judgement], runs: list[Path]) -> None:
    revision, tree, _ = clean_head()
    receipt = {
        "revision": revision,
        "tree": tree,
        "runs": [str(root.relative_to(ROOT)) if root.is_relative_to(ROOT) else str(root) for root in runs],
        "tests": [
            {"run": item.run, "test": item.test, "outcome": item.outcome, "behaviour": item.behaviour}
            | ({"excused": item.excused_by} if item.excused_by else {})
            for item in judgements
        ],
    }
    if subprocess.run(["git", "check-ignore", "-q", str(RECEIPT)], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError(f"{RECEIPT} is not ignored by git; a tracked receipt changes the tree it certifies")
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=RECEIPT.parent, delete=False) as pending:
        pending.write(json.dumps(receipt, indent=2) + "\n")
    Path(pending.name).replace(RECEIPT)


def verify() -> list[str]:
    _, tree, problems = clean_head()
    if not RECEIPT.is_file():
        return [*problems, "no behaviour receipt for this clone; run: just behaviour-gate"]
    receipt = json.loads(RECEIPT.read_text())
    if receipt.get("tree") != tree:
        problems.append(f"the behaviour receipt covers {receipt.get('revision')}, not HEAD; run: just behaviour-gate")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("judge", "certify", "verify"))
    parser.add_argument("runs", nargs="*", type=Path, help="run directories e2e_stack.py --per-test wrote")
    args = parser.parse_args()
    if args.command == "verify":
        problems = verify()
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    if not args.runs:
        parser.error(f"{args.command} needs at least one run directory")
    runs = [root.resolve() for root in args.runs]
    expectations = load_expectations()
    judgements = judge_runs(runs, expectations)
    problems = certification_problems(runs, judgements, expectations) if args.command == "certify" else []
    report(judgements, problems)
    if problems or not all(item.accepted for item in judgements):
        return 1
    if args.command == "certify":
        write_receipt(judgements, runs)
        print(f">> behaviour receipt written for {clean_head()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

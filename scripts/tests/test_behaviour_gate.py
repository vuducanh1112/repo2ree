import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location("behaviour_gate", ROOT / "scripts/publish/behaviour_gate.py")
assert SPEC
assert SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules["behaviour_gate"] = gate
SPEC.loader.exec_module(gate)

HEAD = "a" * 40


def write_run(root: Path, tier: str, tests: dict[str, tuple[str, dict[str, Any] | None]], revision: str = HEAD) -> Path:
    """A per-test run: each test's outcome, and the checker report its recording yields (None: no recording)."""
    root.mkdir(parents=True)
    entries = []
    for index, (name, (outcome, report)) in enumerate(tests.items()):
        directory = f"tests/t{index}"
        (root / directory).mkdir(parents=True)
        (root / directory / "report.json").write_text(json.dumps(report))
        entries.append({"name": name, "outcome": outcome, "directory": directory})
    (root / "run.json").write_text(json.dumps({"tier": tier, "build_revision": revision, "tests": entries}))
    return root


def checker_report(**rules: str) -> dict[str, Any]:
    verdicts = set(rules.values())
    verdict = "violated" if "violated" in verdicts else "inconclusive" if "inconclusive" in verdicts else "passed"
    return {"verdict": verdict, "rules": [{"rule": rule, "verdict": value} for rule, value in rules.items()]}


@pytest.fixture(autouse=True)
def recorded_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "check_recording", lambda directory: json.loads((directory / "report.json").read_text()))
    monkeypatch.setattr(gate, "clean_head", lambda: (HEAD, "tree", []))


def expectation(test: str, violated: tuple[str, ...] = (), inconclusive: tuple[str, ...] = ()) -> dict[str, Any]:
    return {test: gate.Expectation(test, frozenset(violated), frozenset(inconclusive), "known bug")}


def judged(run: Path, expectations: dict[str, Any] | None = None) -> dict[str, Any]:
    return {item.test: item for item in gate.judge_runs([run], expectations or {})}


def test_a_passing_test_with_conforming_behaviour_is_accepted(tmp_path: Path) -> None:
    run = write_run(tmp_path / "run", "e2e-system", {"t": ("passed", checker_report(a="passed", b="not_triggered"))})
    assert judged(run)["t"].accepted


def test_a_passing_test_whose_behaviour_is_violated_is_refused(tmp_path: Path) -> None:
    run = write_run(tmp_path / "run", "e2e-system", {"t": ("passed", checker_report(a="violated", b="inconclusive"))})
    (item,) = judged(run).values()
    assert not item.accepted
    assert item.problems == ["behaviour violated: violated a; inconclusive b"]


@pytest.mark.parametrize(("outcome", "report"), [("failed", checker_report(a="passed")), ("passed", None)])
def test_a_failed_test_or_one_without_a_verdict_is_refused(tmp_path: Path, outcome: str, report: Any) -> None:
    run = write_run(tmp_path / "run", "e2e-system", {"t": (outcome, report)})
    assert not judged(run)["t"].accepted


def test_an_expectation_excuses_exactly_the_rules_it_names(tmp_path: Path) -> None:
    excuse = expectation("t", violated=("a",), inconclusive=("b",))
    exact_report = checker_report(a="violated", b="inconclusive")
    exact = write_run(tmp_path / "exact", "e2e-system", {"t": ("xfailed", exact_report)})
    more = write_run(tmp_path / "more", "e2e-system", {"t": ("xfailed", checker_report(a="violated", c="violated"))})
    fixed = write_run(tmp_path / "fixed", "e2e-system", {"t": ("passed", checker_report(a="passed"))})
    assert judged(exact, excuse)["t"].excused_by == "known bug"
    assert not judged(more, excuse)["t"].accepted
    # A test that now conforms makes its excuse stale: remove it with the fix.
    assert not judged(fixed, excuse)["t"].accepted


def test_certification_needs_every_tier_from_a_clean_head_and_no_unused_expectation(tmp_path: Path) -> None:
    system = write_run(tmp_path / "system", "e2e-system", {"t": ("passed", checker_report(a="passed"))})
    gui = write_run(tmp_path / "gui", "e2e-gui-instant", {"g": ("passed", checker_report(a="passed"))})
    stale = write_run(tmp_path / "stale", "e2e-gui-instant", {"g": ("passed", None)}, revision=HEAD + "-dirty")
    judgements = gate.judge_runs([system, gui], {})

    assert gate.certification_problems([system, gui], judgements, {}) == []
    assert gate.certification_problems([system], judgements, {}) == ["no e2e-gui-instant run among the runs certified"]
    assert gate.certification_problems([system, stale], judgements, {}) == [
        f"stale ran on {HEAD}-dirty, not HEAD {HEAD}"
    ]
    assert gate.certification_problems([system, gui], judgements, expectation("gone")) == [
        "expected-verdicts.toml excuses gone, which no run ran"
    ]


def test_expectations_need_a_reason(tmp_path: Path) -> None:
    path = tmp_path / "expected.toml"
    path.write_text('[[expected]]\ntest = "t"\nviolated = ["a"]\n')
    with pytest.raises(ValueError, match="needs a test and a reason"):
        gate.load_expectations(path)


def test_the_committed_expectations_load() -> None:
    assert all(item.reason.strip() for item in gate.load_expectations().values())

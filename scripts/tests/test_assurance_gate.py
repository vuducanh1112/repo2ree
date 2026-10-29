import json
from pathlib import Path
from typing import Any

import pytest
from scripts.gates import assurance_gate as gate

HEAD = "a" * 40


def write_run(
    root: Path,
    tier: str,
    tests: dict[str, tuple[str, dict[str, Any] | None]],
    revision: str = HEAD,
    selected: tuple[str, ...] = (),
) -> Path:
    """A per-test run: each test's outcome, and the checker report its dossier yields (None: no dossier)."""
    root.mkdir(parents=True)
    entries = []
    for index, (name, (outcome, report)) in enumerate(tests.items()):
        directory = f"tests/t{index}"
        (root / directory).mkdir(parents=True)
        (root / directory / "report.json").write_text(json.dumps(report))
        entries.append({"name": name, "outcome": outcome, "directory": directory})
    record = {"tier": tier, "build_revision": revision, "selected": list(selected), "tests": entries}
    (root / "run.json").write_text(json.dumps(record))
    return root


def checker_report(**rules: str) -> dict[str, Any]:
    verdicts = set(rules.values())
    verdict = "violated" if "violated" in verdicts else "inconclusive" if "inconclusive" in verdicts else "passed"
    return {"verdict": verdict, "rules": [{"rule": rule, "verdict": value} for rule, value in rules.items()]}


@pytest.fixture(autouse=True)
def recorded_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "check_dossier", lambda directory: json.loads((directory / "report.json").read_text()))
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


def test_an_xfail_is_accepted_only_when_excused(tmp_path: Path) -> None:
    run = write_run(tmp_path / "run", "e2e-system", {"t": ("xfailed", checker_report(a="passed"))})
    assert judged(run)["t"].problems == ["xfailed, and expected-verdicts.toml does not excuse it"]
    assert judged(run, expectation("t"))["t"].accepted


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
    faults = write_run(tmp_path / "faults", "e2e-faults", {"f": ("passed", checker_report(a="passed"))})
    stale = write_run(tmp_path / "stale", "e2e-gui-instant", {"g": ("passed", None)}, revision=HEAD + "-dirty")
    judgements = gate.judge_runs([system, gui, faults], {})

    assert gate.certification_problems([system, gui, faults], judgements, {}) == []
    assert gate.certification_problems([system, faults], judgements, {}) == [
        "no e2e-gui-instant run among the runs certified"
    ]
    assert gate.certification_problems([system, gui], judgements, {}) == ["no e2e-faults run among the runs certified"]
    assert gate.certification_problems([system, stale, faults], judgements, {}) == [
        f"stale ran on {HEAD}-dirty, not HEAD {HEAD}"
    ]
    partial = write_run(tmp_path / "partial", "e2e-faults", {"f": ("passed", None)}, selected=("test_x",))
    assert gate.certification_problems([system, gui, partial], judgements, {}) == [
        "partial ran only the tests matching test_x, not its whole tier"
    ]
    assert gate.certification_problems([system, gui, faults], judgements, expectation("gone")) == [
        "expected-verdicts.toml excuses gone, which no run ran"
    ]


def test_expectations_need_a_reason(tmp_path: Path) -> None:
    path = tmp_path / "expected.toml"
    path.write_text('[[expected]]\ntest = "t"\nviolated = ["a"]\n')
    with pytest.raises(ValueError, match="needs a test and a reason"):
        gate.load_expectations(path)


def test_the_committed_expectations_load() -> None:
    assert all(item.reason.strip() for item in gate.load_expectations().values())


def covering(
    report: dict[str, Any], reached: dict[str, int], triggered: dict[str, int] | None = None
) -> dict[str, Any]:
    """A checker report whose evidence reached the given Run edges and triggered the given rules."""
    for rule in report["rules"]:
        rule["triggered"] = (triggered or {}).get(rule["rule"], 0)
    report["coverage"] = {"transitions": {"Run": reached}, "messages": {"dispatch": {"error": 0}}}
    return report


def test_the_suite_must_reach_every_declared_item_it_does_not_excuse(tmp_path: Path) -> None:
    # Each test passes rule b, which nothing triggered; only the suite sees it was never tested.
    first = covering(
        checker_report(a="passed", b="not_triggered"), {"queued -> running": 1, "running -> failed": 0}, {"a": 1}
    )
    second = covering(checker_report(a="passed", b="not_triggered"), {"queued -> running": 0, "running -> failed": 0})
    run = write_run(tmp_path / "run", "e2e-system", {"t": ("passed", first), "u": ("passed", second)})
    judgements = gate.judge_runs([run], {})
    assert all(item.accepted for item in judgements)

    assert gate.coverage_problems(judgements, {}) == [
        "no gated test reaches Run running -> failed",
        "no gated test reaches dispatch: error",
        "no gated test reaches rule:b",
    ]
    excused = {"Run running -> failed": "r", "dispatch: error": "r", "rule:b": "r"}
    assert gate.coverage_problems(judgements, excused) == []


def test_an_unreached_item_a_test_reaches_or_the_spec_dropped_is_stale(tmp_path: Path) -> None:
    report = covering(checker_report(a="passed"), {"queued -> running": 1}, {"a": 1})
    run = write_run(tmp_path / "run", "e2e-system", {"t": ("passed", report)})
    judgements = gate.judge_runs([run], {})
    excused = {"Run queued -> running": "r", "dispatch: error": "r", "Run gone -> away": "r"}
    assert gate.coverage_problems(judgements, excused) == [
        "expected-verdicts.toml declares Run queued -> running unreached, but a test reached it: remove it",
        "expected-verdicts.toml declares Run gone -> away unreached, which the specification does not declare",
    ]


def test_unreached_entries_need_items_and_a_reason_and_name_each_item_once(tmp_path: Path) -> None:
    path = tmp_path / "expected.toml"
    path.write_text('[[unreached]]\nitems = ["rule:a"]\n')
    with pytest.raises(ValueError, match="needs items and a reason"):
        gate.load_unreached(path)
    path.write_text(
        '[[unreached]]\nitems = ["rule:a"]\nreason = "r"\n[[unreached]]\nitems = ["rule:a"]\nreason = "s"\n'
    )
    with pytest.raises(ValueError, match="rule:a is declared unreached twice"):
        gate.load_unreached(path)


def test_the_committed_unreached_items_load() -> None:
    assert all(reason.strip() for reason in gate.load_unreached().values())

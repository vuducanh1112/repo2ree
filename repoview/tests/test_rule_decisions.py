"""Each rule links to the tests that decided it and the operations that triggered it."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.exports import SPEC_EXPORT, Operations, Spec, exported
from repo2ree_repoview.overview.html import rule_link
from repo2ree_repoview.overview.pages.coverage import page_coverage
from repo2ree_repoview.overview.receipt import Decision, Evidence, Exercised, Finding, Receipt, decisions

RUN, PASSING, FAILING = "e2e-system-1", "tests::passing", "tests::lost"


def receipt() -> Receipt:
    return Receipt.model_validate(
        {
            "gate": "assurance-gate",
            "revision": "a" * 40,
            "tree": "b" * 40,
            "runs": [f"test-artifacts/e2e/{RUN}"],
            "tests": [
                {"run": RUN, "test": PASSING, "outcome": "passed", "behaviour": "passed"},
                {"run": RUN, "test": FAILING, "outcome": "xfailed", "behaviour": "violated", "excused": "a bug"},
            ],
            "coverage": {"declared": 1, "reached": 1},
        }
    )


def bundled_test(bundle: Bundle, directory: str, rules: list[dict[str, object]], rees: tuple[str, ...]) -> None:
    verification = bundle.root / directory / "verification"
    verification.mkdir(parents=True)
    (verification / "assurance.json").write_text(json.dumps({"rules": rules}))
    (verification / "assurance.html").write_text("<p>verdicts</p>")
    for ree in rees:
        (bundle.root / directory / "traces").mkdir(exist_ok=True)
        (bundle.root / directory / "traces" / f"{ree}.html").write_text("<p>trace</p>")


def test_each_rule_a_test_triggered_is_decided_by_that_test(tmp_path: Path) -> None:
    bundle = Bundle(tmp_path / "overview", "a" * 40)
    passing, failing = f"evidence/{RUN}/tests/passing", f"evidence/{RUN}/tests/lost"
    ends: dict[str, object] = {"rule": "allocation-ends", "kind": "invariant", "verdict": "passed", "triggered": 2}
    untouched: dict[str, object] = {
        "rule": "sealed-without-stale-evidence",
        "kind": "invariant",
        "verdict": "not_triggered",
    }
    bundled_test(bundle, passing, [ends, untouched], ("ree-1",))
    finding = {"verdict": "violated", "subject": "Allocation a-1", "reason": "still assigned"}
    bundled_test(bundle, failing, [{**ends, "verdict": "violated", "triggered": 1, "findings": [finding]}], ())
    evidence = Evidence(tests={(RUN, PASSING): passing, (RUN, FAILING): failing})

    decided = decisions(bundle, receipt(), evidence)
    assert list(decided) == ["allocation-ends"]  # A rule no test triggered was decided by none.
    held, broken = decided["allocation-ends"]
    assert (held.test, held.verdict, held.excused) == (PASSING, "passed", None)
    assert held.report == f"{passing}/verification/assurance.html"
    assert held.traces == (f"{passing}/traces/ree-1.html",)
    assert (broken.verdict, broken.excused, broken.traces) == ("violated", "a bug", ())
    assert broken.findings == (Finding(verdict="violated", subject="Allocation a-1", reason="still assigned"),)


def test_the_rules_table_links_each_rule_to_its_tests_traces_and_operations(tmp_path: Path) -> None:
    spec = Spec.model_validate_json(exported(SPEC_EXPORT))
    finding = Finding(verdict="violated", subject="Allocation a-1", reason="still assigned")
    decided = {
        "allocation-ends": [
            Decision(
                PASSING, "invariant", "passed", 2, (), None, "t/verification/assurance.html", ("t/traces/r.html",)
            ),
            Decision(FAILING, "invariant", "violated", 1, (finding,), "a bug", None, ()),
        ]
    }
    catalogue = Operations.model_validate(
        {
            "format": "repo2ree-operations/1",
            "lanes": [],
            "operations": [
                {
                    "name": "provision",
                    "outcome": "succeeded",
                    "kind": "setup",
                    "instances": [],
                    "representative": 0,
                    "lines": [],
                    "elsewhere": [],
                    "reach": {},
                    "rules": [{"rule": "allocation-ends", "passed": 2}],
                }
            ],
        }
    )
    exercised = Exercised(Counter(), Counter({"allocation-ends": 3}), Counter())
    body = page_coverage(spec, receipt(), exercised, {}, decided, catalogue).body

    assert '<code id="rule-allocation-ends">allocation-ends</code>' in body
    assert 'href="t/traces/r.html#rule=allocation-ends"' in body
    assert 'href="t/verification/assurance.html"' in body
    assert "excused: a bug" in body
    assert "Allocation a-1: still assigned" in body
    assert 'href="operations.html#op-provision-succeeded"' in body
    # Every invariant has a row, decided or not, so the specification's links always land.
    assert all(f'id="rule-{invariant.id}"' in body for invariant in spec.invariants)
    assert (
        rule_link("allocation-ends") == '<a href="coverage.html#rule-allocation-ends"><code>allocation-ends</code></a>'
    )

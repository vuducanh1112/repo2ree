"""Each rule links to the tests that decided it and the operations that triggered it."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.exports import SPEC_EXPORT, Operations, ShowcaseRuns, Spec, exported
from repo2ree_repoview.overview.html import rule_link
from repo2ree_repoview.overview.pages.coverage import page_coverage, page_showcase_coverage
from repo2ree_repoview.overview.pages.gates import evidence_links
from repo2ree_repoview.overview.receipt import (
    Decision,
    Evidence,
    Exercised,
    Finding,
    Receipt,
    RunRecord,
    TierNeed,
    decisions,
    receipt_tests,
)

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

    decided = decisions(bundle, receipt_tests(receipt()), evidence)
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
    body = page_coverage(
        spec, receipt(), exercised, {}, decided, catalogue, Bundle(tmp_path / "overview", "a" * 40)
    ).body

    assert '<code id="rule-allocation-ends">allocation-ends</code>' in body
    assert 'href="evidence.html?from=coverage#t/traces/r.html#rule=allocation-ends"' in body
    assert 'href="evidence.html?from=coverage#t/verification/assurance.html"' in body
    assert "excused: a bug" in body
    assert "Allocation a-1: still assigned" in body
    assert 'href="operations.html#op-provision-succeeded"' in body
    # Every invariant has a row, decided or not, so the specification's links always land.
    assert all(f'id="rule-{invariant.id}"' in body for invariant in spec.invariants)
    assert (
        rule_link("allocation-ends") == '<a href="coverage.html#rule-allocation-ends"><code>allocation-ends</code></a>'
    )


def test_a_test_links_its_traces_once_whose_page_has_a_tab_per_ree(tmp_path: Path) -> None:
    bundle = Bundle(tmp_path / "overview", "a" * 40)
    bundled_test(bundle, "evidence/one", [], ("ree-1",))
    bundled_test(bundle, "evidence/two", [], ("ree-b", "ree-a"))
    assert evidence_links(bundle, "evidence/one").endswith(
        '<a href="evidence.html?from=assurance-gate#evidence/one/traces/ree-1.html">trace</a>'
    )
    assert evidence_links(bundle, "evidence/two").endswith(
        '<a href="evidence.html?from=assurance-gate#evidence/two/traces/ree-a.html">traces · 2 REEs</a>'
    )
    # The whole dossier's page is the way in, where there is one.
    (bundle.root / "evidence/two/traces/dossier.html").write_text("<p>dossier</p>")
    assert evidence_links(bundle, "evidence/two").endswith(
        '<a href="evidence.html?from=assurance-gate#evidence/two/traces/dossier.html">traces · 2 REEs</a>'
    )


def test_the_showcase_gate_lists_each_showcase_with_its_evidence_and_coverage(tmp_path: Path) -> None:
    spec = Spec.model_validate_json(exported(SPEC_EXPORT))
    showcases = ShowcaseRuns.model_validate(
        {
            "format": "repo2ree-showcase-runs/2",
            "tiers": [
                {
                    "tier": "showcase",
                    "surface": "browser",
                    "environments": [],
                    "recipe": "just test-showcase",
                    "run": None,
                },
                {
                    "tier": "showcase-api",
                    "surface": "api",
                    "environments": ["bare", "docker"],
                    "recipe": "just test-showcase-api",
                    "run": f"test-artifacts/e2e/{RUN}",
                },
            ],
            "showcases": [
                {
                    "name": "python_venv",
                    "kind": "showcase",
                    "environment": "bare",
                    "tests": [
                        {
                            "surface": "api",
                            "workflow": "authoring",
                            "file": "testbed/suites/showcase/python_venv/test_python_venv_authoring.py",
                            "tier": "showcase-api",
                            "run": f"test-artifacts/e2e/{RUN}",
                            "test": PASSING,
                        },
                        {
                            "surface": "browser",
                            "workflow": "review",
                            "file": "gui/tests/showcase/python-venv-review.spec.ts",
                            "tier": "showcase",
                            "run": None,
                            "test": None,
                        },
                    ],
                }
            ],
        }
    )
    record = RunRecord.model_validate(
        {
            "build_revision": "c" * 40,
            "platform": "linux/amd64",
            "tests": [{"name": PASSING, "directory": "tests/p", "outcome": "failed"}],
        }
    )
    decided = {
        "allocation-ends": [
            Decision(PASSING, "invariant", "passed", 2, (), None, "t/verification/assurance.html", ("t/traces/r.html",))
        ]
    }
    exercised = Exercised(Counter(), Counter({"allocation-ends": 2}), Counter())
    bundle = Bundle(tmp_path / "overview", "a" * 40)
    bundled_test(bundle, "t", [], ("r",))

    page = page_showcase_coverage(
        spec,
        showcases,
        {f"test-artifacts/e2e/{RUN}": record},
        {(RUN, PASSING): "passed"},
        exercised,
        decided,
        Evidence(tests={(RUN, PASSING): "t"}),
        bundle,
        [TierNeed("showcase-api", "linux/amd64", "test-showcase-api", None, None)],
    )

    assert (page.slug, page.title) == ("showcase-gate", "Showcase gate")
    assert '<h4 id="showcase-python_venv"><code>python_venv</code> · API on <code>bare</code></h4>' in page.body
    assert "test_python_venv_authoring.py" in page.body
    assert 'href="evidence.html?from=showcase-gate#t/traces/r.html"' in page.body
    assert "not in this clone</span>: <code>just test-showcase</code>" in page.body
    # A test whose behaviour passed but which itself failed says both.
    assert '<span class="no">failed</span>' in page.body
    assert '<span class="no">needed</span>: <code>just test-showcase-api</code>' in page.body
    assert "<code>bare</code>, <code>docker</code>" in page.body
    assert "<code>just test-showcase</code>" in page.body
    assert f"<code>{RUN}</code>" in page.body
    assert '<span class="no">1 failed</span>' in page.body
    assert 'href="evidence.html?from=showcase-gate#t/verification/assurance.html"' in page.body
    assert "operations.html#" not in page.body
    assert "1 tests in 1 runs" in page.teaser

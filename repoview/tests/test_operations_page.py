"""The operations page draws traceview's catalogue: each operation's reach, its sequence, and what it left out."""

from __future__ import annotations

from pathlib import Path

from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.exports import Operations, exported, operations_export
from repo2ree_repoview.overview.pages.operations import page_operations
from repo2ree_repoview.overview.receipt import Evidence, Receipt

RECEIPT = Receipt.model_validate(
    {
        "gate": "assurance-gate",
        "revision": "a" * 40,
        "tree": "b" * 40,
        "runs": ["test-artifacts/e2e/run"],
        "tests": [],
        "coverage": {"declared": 1, "reached": 1},
    }
)
LANES = [
    {"id": "api", "label": "API", "process": "api process"},
    {"id": "supervisor", "label": "Supervisor", "process": "api process"},
    {"id": "workbench", "label": "Workbench", "process": "workbench"},
]


def instance(source: str, outcome: str = "succeeded", duration: float = 1.0) -> dict[str, object]:
    return {
        "source": source,
        "test": f"tests::{source}",
        "ree": "ree-1",
        "outcome": outcome,
        "duration": duration,
        "verdict": "passed",
    }


CATALOGUE = Operations.model_validate(
    {
        "format": "repo2ree-operations/1",
        "lanes": LANES,
        "operations": [
            {
                "name": "build_runtime",
                "outcome": "succeeded",
                "kind": "operation",
                "instances": [instance("v1"), instance("v2", duration=2.0)],
                "representative": 0,
                "lines": [
                    {"lane": "api", "label": "build_runtime → requested", "provenance": "journal", "t": 0, "seen": 2},
                    {
                        "lane": "supervisor",
                        "to": "workbench",
                        "label": "exec_action · build_runtime",
                        "provenance": "journal",
                        "t": 0.1,
                        "seen": 2,
                    },
                    {"lane": "workbench", "label": "… without spans", "provenance": "gap", "t": 0.2, "seen": 1},
                ],
                "elsewhere": [
                    {"lane": "api", "label": "build_runtime → canceling", "provenance": "journal", "t": 0.3, "seen": 1}
                ],
                "reach": {"api": "checked", "supervisor": "exchanged", "workbench": "exchanged"},
                "rules": [{"rule": "api-success-is-recorded", "passed": 2}],
            },
            {
                "name": "release",
                "outcome": "released",
                "kind": "setup",
                "instances": [instance("v1", "released")],
                "representative": 0,
                "lines": [],
                "elsewhere": [],
                "reach": {"api": "none", "supervisor": "none", "workbench": "none"},
                "rules": [],
            },
        ],
        "undrawn": [{"source": "v3", "test": "tests::lost", "verdict": "violated", "reason": "no REE history"}],
    }
)


def test_the_export_reads_as_traceview_wrote_it() -> None:
    catalogue = Operations.model_validate_json(exported(operations_export([])))
    assert (catalogue.operations, catalogue.undrawn) == ((), ())
    assert [lane.id for lane in catalogue.lanes][:2] == ["client", "api"]


def test_each_operation_says_how_far_its_checked_evidence_reaches(tmp_path: Path) -> None:
    page = page_operations(CATALOGUE, RECEIPT, Bundle(tmp_path / "overview", "a" * 40), Evidence())
    assert page.slug == "operations"
    assert page.teaser == "2 operations in 2 outcomes, across components"
    assert 'href="#op-build_runtime-succeeded"' in page.body
    assert 'title="API: checked"' in page.body
    assert 'title="Workbench: exchanged"' in page.body
    # Release has no sequence, so it claims no reach rather than none everywhere.
    assert 'title="Workbench: none"' not in page.body
    assert "no sequence: only the journal records it" in page.body


def test_a_sequence_marks_the_lines_only_some_runs_show(tmp_path: Path) -> None:
    body = page_operations(CATALOGUE, RECEIPT, Bundle(tmp_path / "overview", "a" * 40), Evidence()).body
    assert body.count('<svg class="seq"') == 1
    assert '<g class="p-gap partial">' in body
    assert "exec_action · build_runtime" in body
    assert "Lines other runs show and this one does not (1)" in body
    assert "build_runtime → canceling" in body


def test_what_was_not_drawn_is_said_with_its_reason(tmp_path: Path) -> None:
    body = page_operations(CATALOGUE, RECEIPT, Bundle(tmp_path / "overview", "a" * 40), Evidence()).body
    assert "tests::lost" in body
    assert "no REE history" in body


def test_without_a_receipt_the_page_says_how_to_get_one(tmp_path: Path) -> None:
    empty = Operations.model_validate({"format": "repo2ree-operations/1", "lanes": LANES, "operations": []})
    page = page_operations(empty, None, Bundle(tmp_path / "overview", "a" * 40), Evidence())
    assert "just assurance-gate" in page.body

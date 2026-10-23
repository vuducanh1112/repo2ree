"""The gates' receipts, the last assurance-gate receipt, and the test evidence it names."""

from __future__ import annotations

import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import Field

from repo2ree_repoview.documents import Document
from repo2ree_repoview.overview.bundle import Bundle, Origin
from repo2ree_repoview.repository import ROOT, Head

RECEIPTS = ROOT / ".receipts"
RECEIPT = RECEIPTS / "assurance-gate.json"
EXPECTATIONS = ROOT / "assurance/checker/expected-verdicts.toml"


class GateReceipt(Document):
    """The header every gate's receipt shares (scripts/gates/receipts.py)."""

    gate: str
    revision: str | None = None
    tree: str


class ReceiptTest(Document):
    run: str
    test: str
    outcome: str
    behaviour: str
    excused: str | None = None


class ReceiptCoverage(Document):
    declared: int
    reached: int


class Receipt(GateReceipt):
    """The assurance gate's receipt: the runs and verdicts it certified HEAD's tree by."""

    revision: str
    runs: tuple[str, ...]
    tests: tuple[ReceiptTest, ...]
    coverage: ReceiptCoverage


def read_gate_receipt(gate: str) -> GateReceipt | None:
    path = RECEIPTS / f"{gate}.json"
    return GateReceipt.model_validate_json(path.read_bytes()) if path.is_file() else None


def read_receipt() -> Receipt | None:
    return Receipt.model_validate_json(RECEIPT.read_bytes()) if RECEIPT.is_file() else None


def reached(receipt: Receipt | None) -> str:
    """How much of the specification the receipt's tests reached, as the pages say it."""
    coverage = receipt.coverage if receipt else None
    return f"{coverage.reached} of {coverage.declared}" if coverage else "? of ?"


@dataclass(frozen=True)
class ReceiptState:
    """Whether one gate's receipt covers what is checked out now."""

    name: str
    recipe: str
    state: Literal["current", "stale", "missing"]
    detail: str


def receipt_states(head: Head, receipt: Receipt | None) -> list[ReceiptState]:
    never = "never run in this clone"
    found: list[ReceiptState] = []
    commit = read_gate_receipt("commit-gate")
    if commit is not None:
        current = commit.tree in {head.tree, head.index_tree}
        state: Literal["current", "stale"] = "current" if current else "stale"
        found.append(ReceiptState("Commit gate", "just commit-gate", state, f"tree {commit.tree[:10]}"))
    else:
        found.append(ReceiptState("Commit gate", "just commit-gate", "missing", never))
    if receipt is not None:
        detail = f"{receipt.revision[:10]}: {len(receipt.tests)} tests"
        if receipt.tree != head.tree:
            found.append(ReceiptState("Assurance gate", "just assurance-gate", "stale", detail))
        else:
            if head.dirty:
                detail += "; covers HEAD, not the uncommitted changes"
            found.append(ReceiptState("Assurance gate", "just assurance-gate", "current", detail))
    else:
        found.append(ReceiptState("Assurance gate", "just assurance-gate", "missing", never))
    publish = read_gate_receipt("publish-gate")
    if publish is not None:
        state = "current" if publish.tree == head.tree else "stale"
        detail = f"{(publish.revision or '?')[:10]}: local image set"
        found.append(ReceiptState("Publish gate", "just publish-gate", state, detail))
    else:
        found.append(ReceiptState("Publish gate", "just publish-gate", "missing", never))
    return found


class RunTest(Document):
    name: str
    directory: str


class RunRecord(Document):
    build_revision: str = ""
    tests: tuple[RunTest, ...] = ()


# What a test's evidence holds, by whether the overview copies it or only names it by hash.
COPIED = (
    "test.json",
    "junit.xml",
    "logs",
    "verification",
    "traces",
    "dossier/manifest.json",
    "dossier/journal",
    "dossier/stores",
)
REFERENCED = ("dossier/rees", "dossier/telemetry", "artifacts")


@dataclass(frozen=True)
class Evidence:
    """The receipt's runs as bundled, and where each (run, test) landed in the bundle."""

    runs: tuple[Path, ...] = ()
    tests: dict[tuple[str, str], str] = field(default_factory=dict)


def bundle_evidence(bundle: Bundle, receipt: Receipt | None) -> Evidence:
    """Copy the receipt and its runs' evidence into the bundle."""
    if receipt is None:
        return Evidence()
    bundle.copy(RECEIPT, "evidence/assurance-gate.json", Origin(kind="receipt"))
    runs: list[Path] = []
    tests: dict[tuple[str, str], str] = {}
    for run in (ROOT / name for name in receipt.runs):
        if not (run / "run.json").is_file():
            continue
        record = RunRecord.model_validate_json((run / "run.json").read_bytes())
        origin = Origin(run=run.name, run_revision=record.build_revision)
        bundle.copy(run / "run.json", f"evidence/{run.name}/run.json", origin)
        for test in record.tests:
            target = f"evidence/{run.name}/{test.directory}"
            for part in COPIED:
                source = run / test.directory / part
                if source.is_dir():
                    bundle.copy_tree(source, f"{target}/{part}", origin)
                else:
                    bundle.copy(source, f"{target}/{part}", origin)
            for part in REFERENCED:
                bundle.reference(run / test.directory / part, origin)
            tests[(run.name, test.name)] = target
        runs.append(bundle.root / "evidence" / run.name)
    return Evidence(tuple(runs), tests)


class _Exercised(Document):
    transitions: dict[str, dict[str, int]] = Field(default_factory=dict)
    messages: dict[str, dict[str, int]] = Field(default_factory=dict)


class _RuleCount(Document):
    rule: str
    triggered: int = 0


class _Extra(Document):
    subject: str
    fact: str | None = None
    count: int


class ConformanceReport(Document):
    coverage: _Exercised = _Exercised()
    rules: tuple[_RuleCount, ...] = ()
    extras: tuple[_Extra, ...] = ()


@dataclass(frozen=True)
class Exercised:
    """Summed over the receipt's tests: how often each edge and message was recorded, each rule triggered,
    and each record beyond the vocabulary seen."""

    edges: Counter[str]
    rules: Counter[str]
    extras: Counter[tuple[str, str]]

    @classmethod
    def over(cls, evidence: Evidence) -> Exercised:
        edges: Counter[str] = Counter()
        rules: Counter[str] = Counter()
        extras: Counter[tuple[str, str]] = Counter()
        for run in evidence.runs:
            for path in run.glob("tests/*/verification/conformance.json"):
                report = ConformanceReport.model_validate_json(path.read_bytes())
                for machine, counts in report.coverage.transitions.items():
                    edges.update({f"{machine} {edge}": count for edge, count in counts.items()})
                for boundary, counts in report.coverage.messages.items():
                    edges.update({f"{boundary}: {message}": count for message, count in counts.items()})
                rules.update({rule.rule: rule.triggered for rule in report.rules})
                for extra in report.extras:
                    extras[(extra.subject, extra.fact or "")] += extra.count
        return cls(edges, rules, extras)


class _Unreached(Document):
    items: tuple[str, ...]
    reason: str


class _Expectations(Document):
    unreached: tuple[_Unreached, ...] = ()


def unreached() -> dict[str, str]:
    """Each item no gated test reaches, with the reason the expectations give."""
    declared = _Expectations.model_validate(tomllib.loads(EXPECTATIONS.read_text()))
    return {item: entry.reason for entry in declared.unreached for item in entry.items}

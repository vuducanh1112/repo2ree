"""The gates' certificates, the last behaviour receipt, and the test evidence it names."""

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

CERTIFICATES = ROOT / ".validation-certificates"
RECEIPT = CERTIFICATES / "behaviour-ok"
EXPECTATIONS = ROOT / "conformance/expected-verdicts.toml"


class ReceiptTest(Document):
    run: str
    test: str
    outcome: str
    behaviour: str
    excused: str = ""


class ReceiptCoverage(Document):
    declared: int
    reached: int


class Receipt(Document):
    revision: str
    tree: str
    runs: tuple[str, ...]
    tests: tuple[ReceiptTest, ...]
    coverage: ReceiptCoverage | None = None


def read_receipt() -> Receipt | None:
    return Receipt.model_validate_json(RECEIPT.read_bytes()) if RECEIPT.is_file() else None


def reached(receipt: Receipt | None) -> str:
    """How much of the specification the receipt's tests reached, as the pages say it."""
    coverage = receipt.coverage if receipt else None
    return f"{coverage.reached} of {coverage.declared}" if coverage else "? of ?"


@dataclass(frozen=True)
class Certificate:
    name: str
    recipe: str
    state: Literal["current", "stale", "missing"]
    detail: str


def certificates(head: Head, receipt: Receipt | None) -> list[Certificate]:
    never = "never run in this clone"
    found: list[Certificate] = []
    commit = CERTIFICATES / "commit-gate-ok"
    if commit.is_file():
        tree = commit.read_text().strip()
        current = tree in {head.tree, head.index_tree}
        found.append(
            Certificate("Commit gate", "just commit-gate", "current" if current else "stale", f"tree {tree[:10]}")
        )
    else:
        found.append(Certificate("Commit gate", "just commit-gate", "missing", never))
    if receipt is not None:
        detail = f"{receipt.revision[:10]}: {len(receipt.tests)} tests"
        if receipt.tree != head.tree:
            found.append(Certificate("Behaviour gate", "just behaviour-gate", "stale", detail))
        elif head.dirty:
            detail += "; covers HEAD, not the uncommitted changes"
            found.append(Certificate("Behaviour gate", "just behaviour-gate", "current", detail))
        else:
            found.append(Certificate("Behaviour gate", "just behaviour-gate", "current", detail))
    else:
        found.append(Certificate("Behaviour gate", "just behaviour-gate", "missing", never))
    publish = CERTIFICATES / "publish-gate-ok"
    if publish.is_file():
        rows = dict(line.split("\t") for line in publish.read_text().splitlines() if line.count("\t") == 1)
        current = rows.get("tree") == head.tree
        detail = f"{rows.get('revision', '?')[:10]}: local image set"
        found.append(Certificate("Publish gate", "just publish-gate", "current" if current else "stale", detail))
    else:
        found.append(Certificate("Publish gate", "just publish-gate", "missing", never))
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
    "recording/manifest.json",
    "recording/journal",
    "recording/stores",
)
REFERENCED = ("recording/rees", "recording/telemetry", "artifacts")


@dataclass(frozen=True)
class Evidence:
    """The receipt's runs as bundled, and where each (run, test) landed in the bundle."""

    runs: tuple[Path, ...] = ()
    tests: dict[tuple[str, str], str] = field(default_factory=dict)


def bundle_evidence(bundle: Bundle, receipt: Receipt | None) -> Evidence:
    """Copy the receipt and its runs' evidence into the bundle."""
    if receipt is None:
        return Evidence()
    bundle.copy(RECEIPT, "evidence/behaviour-ok.json", Origin(kind="receipt"))
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

"""The gates' receipts, the last assurance-gate receipt, and the test evidence it names."""

from __future__ import annotations

import os
import tomllib
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import Field

from repo2ree_repoview.documents import Document
from repo2ree_repoview.overview.bundle import Bundle, Origin, source_name
from repo2ree_repoview.repository import ROOT, Head

RECEIPTS = ROOT / ".receipts"
RECEIPT = RECEIPTS / "assurance-gate.json"
POLICY = ROOT / "scripts/gates/policy.toml"
# The platforms a published image set carries, as the justfile defaults them.
PUBLISH_PLATFORMS = tuple(os.environ.get("PUBLISH_PLATFORMS", "linux/amd64 linux/arm64").split())
EXPECTATIONS = ROOT / "assurance/checker/expected-verdicts.toml"
# A report of each run, assessed and drawn beside it (`just visualize-behaviour`), laid out like the
# run: <run>/run.json with the verdicts and the commit that assessed them, <run>/<test>/{verification,traces}.
REPORTS = ROOT / "reports/behaviour"


class GateReceipt(Document):
    """The header every gate's receipt shares (scripts/gates/receipts.py)."""

    gate: str
    revision: str | None = None
    tree: str
    # A publish-gate receipt's: the platform of the images it certifies.
    platform: str = ""


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


class TierReceipt(GateReceipt):
    """A tier receipt (scripts/gates/tiers.py): one tier's run, certified on a tree and platform."""

    tier: str
    machine: str = ""
    run: str = ""
    tests: int = 0
    skipped: int = 0
    judged: bool = False
    written: str = ""


def tier_receipts() -> list[TierReceipt]:
    """Every tier receipt in this clone, for any tree."""
    return [TierReceipt.model_validate_json(path.read_bytes()) for path in sorted(RECEIPTS.glob("tiers/*/*.json"))]


@dataclass(frozen=True)
class TierNeed:
    """One tier receipt a gate needs, where (a platform, ``any``, or ``here``), and what meets it for HEAD."""

    tier: str
    place: str
    recipe: str
    current: TierReceipt | None
    last: TierReceipt | None


def gate_needs(head: Head, found: list[TierReceipt]) -> dict[str, list[TierNeed]]:
    """For each gate the policy names, the tier receipts it needs and the ones that meet them."""
    policy = tomllib.loads(POLICY.read_text()) if POLICY.is_file() else {}
    recipes = {name: str(entry.get("recipe", "")) for name, entry in policy.get("tiers", {}).items()}
    needs: dict[str, list[TierNeed]] = {}
    for gate, entry in policy.get("gates", {}).items():
        needs[gate] = []
        for tier, where in entry.get("tiers", {}).items():
            places = PUBLISH_PLATFORMS if where in {"each", "here"} else ("any",)
            for place in places:
                matching = [r for r in found if r.tier == tier and place in {"any", r.platform}]
                current = next((r for r in matching if r.tree == head.tree), None)
                last = max(matching, key=lambda r: r.written, default=None)
                label = {"each": place, "here": f"{place}, gated there", "any": "any platform"}[where]
                needs[gate].append(TierNeed(tier, label, recipes.get(tier, ""), current, last))
    return needs


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
    showcase = gate_needs(head, tier_receipts()).get("showcase-gate", [])
    if showcase:
        proven = [need for need in showcase if need.current is not None]
        showcase_state: Literal["current", "stale", "missing"] = (
            "current"
            if len(proven) == len(showcase)
            else ("stale" if proven or any(n.last for n in showcase) else "missing")
        )
        places = list(dict.fromkeys(need.place for need in showcase))
        done = {place: all(n.current for n in showcase if n.place == place) for place in places}
        detail = f"{sum(done.values())} of {len(places)} platforms proven: " + ", ".join(
            f"{place} {'ok' if ok else 'needed'}" for place, ok in done.items()
        )
        found.append(ReceiptState("Showcase gate", "just showcase-gate", showcase_state, detail))
    # One per platform, each from a machine of that platform (scripts/gates/publish_gate.py).
    published = [
        GateReceipt.model_validate_json(path.read_bytes()) for path in sorted(RECEIPTS.glob("publish-gate-*.json"))
    ]
    for publish in published:
        state = "current" if publish.tree == head.tree else "stale"
        detail = f"{(publish.revision or '?')[:10]}: {publish.platform or 'local'} image set"
        found.append(ReceiptState(f"Publish gate ({publish.platform})", "just publish-gate", state, detail))
    if not published:
        found.append(ReceiptState("Publish gate", "just publish-gate", "missing", never))
    return found


class RunTest(Document):
    name: str
    directory: str
    outcome: str = ""
    rees: tuple[str, ...] = ()
    behaviour: str | None = None


class RunRecord(Document):
    build_revision: str = ""
    platform: str = ""
    # In a report of the run: the commit whose checker assessed it, "" from a dirty tree.
    assessed_revision: str = ""
    tests: tuple[RunTest, ...] = ()


# What a test's evidence holds, by whether the overview copies it or only names it by hash; and what this
# tree's report on it holds, copied in its place beside it.
COPIED = (
    "test.json",
    "junit.xml",
    "logs",
    "dossier/manifest.json",
    "dossier/journal",
    "dossier/stores",
)
REFERENCED = ("dossier/rees", "dossier/telemetry", "artifacts")
REPORTED = ("verification", "traces")


@dataclass(frozen=True)
class Evidence:
    """The receipt's runs as bundled, and each test's bundled folder by (run, test) and by verification path."""

    runs: tuple[Path, ...] = ()
    tests: dict[tuple[str, str], str] = field(default_factory=dict)
    verifications: dict[str, str] = field(default_factory=dict)


def runs_on_disk(names: Iterable[str]) -> Iterator[tuple[Path, RunRecord]]:
    """The runs named, from the repository root, that are still on disk, with their records."""
    for run in (ROOT / name for name in names):
        if (run / "run.json").is_file():
            yield run, RunRecord.model_validate_json((run / "run.json").read_bytes())


def gate_runs(receipt: Receipt | None) -> Iterator[tuple[Path, RunRecord]]:
    """The receipt's runs that are still on disk, with their records."""
    return runs_on_disk(receipt.runs if receipt else ())


@dataclass(frozen=True)
class TestRef:
    """One test whose verdicts a coverage page sums: its run's name, its own, and the excuse it was judged with."""

    run: str
    test: str
    excused: str | None = None


def receipt_tests(receipt: Receipt | None) -> tuple[TestRef, ...]:
    return tuple(TestRef(test.run, test.test, test.excused) for test in receipt.tests) if receipt else ()


def run_tests(runs: Iterable[tuple[Path, RunRecord]]) -> tuple[TestRef, ...]:
    return tuple(TestRef(run.name, test.name) for run, record in runs for test in record.tests)


def reported(run: Path, test: RunTest, reports: Path = REPORTS) -> Path:
    """Where this tree's report on a gated test goes: its verification and its traces."""
    return reports / run.name / test.directory


def verification_of(run: Path, test: RunTest) -> str | None:
    """Where this tree's verification of a test is, from the repository root; None when its dossier was not checked."""
    verification = reported(run, test) / "verification"
    return source_name(verification) if (verification / "verification.json").is_file() else None


def judged_now(reports: Path = REPORTS) -> dict[tuple[str, str], str] | None:
    """This tree's verdict on each gated test, by (run, test) as the receipt names them; None before any report."""
    if not reports.is_dir():
        return None
    verdicts: dict[tuple[str, str], str] = {}
    for record in sorted(reports.glob("*/run.json")):
        run = RunRecord.model_validate_json(record.read_bytes())
        verdicts |= {(record.parent.name, test.name): test.behaviour or "missing" for test in run.tests}
    return verdicts


def gate_verifications(receipt: Receipt | None) -> list[str]:
    """Every verification of the receipt's runs, as the catalogue of operations is folded from them."""
    return [
        found for run, record in gate_runs(receipt) for test in record.tests if (found := verification_of(run, test))
    ]


def bundle_evidence(bundle: Bundle, receipt: Receipt | None) -> Evidence:
    """Copy the receipt and its runs' evidence into the bundle."""
    if receipt is None:
        return Evidence()
    bundle.copy(RECEIPT, "evidence/assurance-gate.json", Origin(kind="receipt"))
    return bundle_runs(bundle, gate_runs(receipt))


def bundle_runs(bundle: Bundle, chosen: Iterable[tuple[Path, RunRecord]]) -> Evidence:
    """Copy these runs' evidence into the bundle."""
    runs: list[Path] = []
    tests: dict[tuple[str, str], str] = {}
    verifications: dict[str, str] = {}
    for run, record in chosen:
        origin = Origin(run=run.name, run_revision=record.build_revision)
        assessed = REPORTS / run.name / "run.json"
        assessed_revision = (
            RunRecord.model_validate_json(assessed.read_bytes()).assessed_revision if assessed.is_file() else ""
        )
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
            report = origin.model_copy(update={"kind": "report", "revision": assessed_revision})
            for part in REPORTED:
                bundle.copy_tree(reported(run, test) / part, f"{target}/{part}", report)
            tests[(run.name, test.name)] = target
            if found := verification_of(run, test):
                verifications[found] = target
        runs.append(bundle.root / "evidence" / run.name)
    return Evidence(tuple(runs), tests, verifications)


class _Exercised(Document):
    transitions: dict[str, dict[str, int]] = Field(default_factory=dict)
    messages: dict[str, dict[str, int]] = Field(default_factory=dict)


class Finding(Document):
    verdict: str
    subject: str = ""
    reason: str = ""


class _RuleCount(Document):
    rule: str
    kind: str = ""
    verdict: str = "not_triggered"
    triggered: int = 0
    findings: tuple[Finding, ...] = ()


class _Extra(Document):
    subject: str
    fact: str | None = None
    count: int


class _MoveCount(Document):
    kind: str
    machine: str
    source: str
    target: str
    operation: str
    count: int
    allowed: bool


class _AggregateResult(Document):
    aggregate: str
    instances: int = 0
    moves: tuple[_MoveCount, ...] = ()
    findings: tuple[Finding, ...] = ()


class AssuranceReport(Document):
    coverage: _Exercised = _Exercised()
    rules: tuple[_RuleCount, ...] = ()
    extras: tuple[_Extra, ...] = ()
    # None in a report from a checker that did not report aggregates yet.
    aggregates: tuple[_AggregateResult, ...] | None = None


def assurance_reports(evidence: Evidence) -> Iterator[AssuranceReport]:
    """Every test's report in the receipt's runs, as the bundle holds them."""
    for run in evidence.runs:
        for path in sorted(run.glob("tests/*/verification/assurance.json")):
            yield AssuranceReport.model_validate_json(path.read_bytes())


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
        for report in assurance_reports(evidence):
            for machine, counts in report.coverage.transitions.items():
                edges.update({f"{machine} {edge}": count for edge, count in counts.items()})
            for boundary, counts in report.coverage.messages.items():
                edges.update({f"{boundary}: {message}": count for message, count in counts.items()})
            rules.update({rule.rule: rule.triggered for rule in report.rules})
            for extra in report.extras:
                extras[(extra.subject, extra.fact or "")] += extra.count
        return cls(edges, rules, extras)


@dataclass(frozen=True)
class Move:
    """One part of an aggregate moving along one edge by one operation; ``machine`` is the part's name."""

    machine: str
    source: str
    target: str
    operation: str


@dataclass(frozen=True)
class AggregateMoves:
    """Summed over the receipt's tests: how often each operation moved each part of one aggregate.

    ``recorded`` is False when no report carried aggregates (a checker from before they were
    reported), so an empty tally is never mistaken for nothing having moved.
    """

    aggregate: str
    recorded: bool
    instances: int
    counts: Counter[Move]
    disallowed: tuple[Finding, ...]

    def of(self, machine: str) -> Counter[Move]:
        return Counter({move: count for move, count in self.counts.items() if move.machine == machine})

    @classmethod
    def over(cls, evidence: Evidence, aggregate: str) -> AggregateMoves:
        recorded, instances = False, 0
        counts: Counter[Move] = Counter()
        disallowed: list[Finding] = []
        for report in assurance_reports(evidence):
            recorded = recorded or report.aggregates is not None
            for result in report.aggregates or ():
                if result.aggregate != aggregate:
                    continue
                instances += result.instances
                disallowed.extend(result.findings)
                for moves in result.moves:
                    counts[Move(moves.machine, moves.source, moves.target, moves.operation)] += moves.count
        return cls(aggregate, recorded, instances, counts, tuple(disallowed))


@dataclass(frozen=True)
class Decision:
    """One test's verdict on one rule; paths are relative to the bundle."""

    test: str
    kind: str
    verdict: str
    triggered: int
    findings: tuple[Finding, ...]
    excused: str | None
    report: str | None
    traces: tuple[str, ...]


def decisions(bundle: Bundle, tests: Iterable[TestRef], evidence: Evidence) -> dict[str, list[Decision]]:
    """Each triggered rule with the tests that decided it, in the order given."""
    decided: dict[str, list[Decision]] = {}
    for test in tests:
        directory = evidence.tests.get((test.run, test.test))
        if directory is None or not (bundle.root / directory / "verification/assurance.json").is_file():
            continue
        report = bundle.root / directory / "verification/assurance.json"
        page = f"{directory}/verification/assurance.html"
        traces = tuple(
            f"{directory}/traces/{path.name}" for path in sorted((bundle.root / directory / "traces").glob("*.html"))
        )
        for rule in AssuranceReport.model_validate_json(report.read_bytes()).rules:
            if rule.verdict == "not_triggered":
                continue
            decided.setdefault(rule.rule, []).append(
                Decision(
                    test=test.test,
                    kind=rule.kind,
                    verdict=rule.verdict,
                    triggered=rule.triggered,
                    findings=rule.findings,
                    excused=test.excused if rule.verdict != "passed" else None,
                    report=page if (bundle.root / page).is_file() else None,
                    traces=traces,
                )
            )
    return decided


class _Unreached(Document):
    items: tuple[str, ...]
    reason: str


class _Expectations(Document):
    unreached: tuple[_Unreached, ...] = ()


def unreached() -> dict[str, str]:
    """Each item no gated test reaches, with the reason the expectations give."""
    declared = _Expectations.model_validate(tomllib.loads(EXPECTATIONS.read_text()))
    return {item: entry.reason for entry in declared.unreached for item in entry.items}


def main() -> int:
    """Print every verification of the assurance-gate receipt's runs, one a line, from the repository root."""
    for found in gate_verifications(read_receipt()):
        print(found)
    return 0

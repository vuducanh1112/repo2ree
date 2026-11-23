from __future__ import annotations

from typing import Literal

from repo2ree_assurance_checker.evidence import Event, EvidenceModel, Source
from repo2ree_assurance_checker.spec import CREATED, MachineKind

type Verdict = Literal["passed", "violated", "inconclusive", "not_triggered"]
type FindingVerdict = Literal["violated", "inconclusive"]

INITIAL = CREATED


class Finding(EvidenceModel):
    verdict: FindingVerdict
    subject: str
    reason: str
    evidence: tuple[str, ...] = ()


class RuleResult(EvidenceModel):
    rule: str
    kind: Literal["evidence", "machine", "boundary", "invariant", "reconciliation", "aggregate", "document"]
    summary: str
    triggered: int = 0
    open: int = 0
    findings: tuple[Finding, ...] = ()

    @property
    def verdict(self) -> Verdict:
        if any(finding.verdict == "violated" for finding in self.findings):
            return "violated"
        if self.findings:
            return "inconclusive"
        return "passed" if self.triggered else "not_triggered"


class Extra(EvidenceModel):
    subject: str
    fact: str | None = None
    count: int
    evidence: tuple[str, ...] = ()


class Coverage(EvidenceModel):
    transitions: dict[str, dict[str, int]]
    messages: dict[str, dict[str, int]]


class MoveCount(EvidenceModel):
    kind: MachineKind
    machine: str
    source: str
    target: str
    operation: str
    count: int
    allowed: bool


class AggregateResult(EvidenceModel):
    aggregate: str
    instances: int
    moves: tuple[MoveCount, ...] = ()
    files: int = 0
    committed: int = 0
    signatures: int = 0
    findings: tuple[Finding, ...] = ()


class Part(EvidenceModel):
    name: str
    machine: str
    item: str = ""
    kind: MachineKind
    group: str


class StateStep(EvidenceModel):
    operation: str
    ref: str
    states: dict[str, str]
    moved: tuple[str, ...]


class AggregateHistory(EvidenceModel):
    aggregate: str
    instance: str
    parts: tuple[Part, ...]
    steps: tuple[StateStep, ...]


class CheckResult(EvidenceModel):
    spec_digest: str
    sources: tuple[Source, ...]
    rules: tuple[RuleResult, ...]
    coverage: Coverage
    vocabulary_digest: str = ""
    extras: tuple[Extra, ...] = ()
    aggregates: tuple[AggregateResult, ...] = ()

    @property
    def verdict(self) -> Verdict:
        verdicts = {rule.verdict for rule in self.rules}
        if "violated" in verdicts:
            return "violated"
        if "inconclusive" in verdicts:
            return "inconclusive"
        if not any(rule.triggered for rule in self.rules if rule.kind not in {"evidence", "reconciliation"}):
            return "inconclusive"
        return "passed"

    @property
    def exit_code(self) -> int:
        return {"violated": 1, "inconclusive": 2}.get(self.verdict, 0)


class Judgement(EvidenceModel):
    rule: str
    event: str
    subject: str
    key: str
    verdict: Literal["passed", "violated", "inconclusive"]
    findings: tuple[Finding, ...] = ()


def edge(source: str | None, target: str) -> str:
    return f"{source or INITIAL} -> {target}"


def finding(verdict: FindingVerdict, subject: str, reason: str, *events: Event) -> Finding:
    return Finding(verdict=verdict, subject=subject, reason=reason, evidence=tuple(event.ref for event in events))

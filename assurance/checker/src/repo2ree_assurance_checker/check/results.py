"""What checking finds: each finding, each rule's result, the coverage, and the check as a whole."""

from __future__ import annotations

from typing import Literal

from repo2ree_assurance_checker.evidence import Event, EvidenceModel, Source
from repo2ree_assurance_checker.spec import (
    CREATED,
)

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
    kind: Literal["evidence", "machine", "boundary", "invariant", "reconciliation"]
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
    """What owners recorded beyond the vocabulary: a subject it does not declare, or a fact of one it does."""

    subject: str
    fact: str | None = None  # None: the whole subject is undeclared.
    count: int
    evidence: tuple[str, ...] = ()


class Coverage(EvidenceModel):
    """How often each declared edge and message was observed; zero marks a gap."""

    transitions: dict[str, dict[str, int]]
    messages: dict[str, dict[str, int]]


class CheckResult(EvidenceModel):
    spec_digest: str
    sources: tuple[Source, ...]
    rules: tuple[RuleResult, ...]
    coverage: Coverage
    # The contract the evidence was judged against; a journal's own stamp is provenance only.
    vocabulary_digest: str = ""
    extras: tuple[Extra, ...] = ()

    @property
    def verdict(self) -> Verdict:
        """A check in which no behavioural rule triggered proves nothing, so it is inconclusive."""
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
    """One invariant occurrence and its verdict, addressed by the event that triggered it."""

    rule: str
    event: str  # Event.ref of the trigger; Git events of one commit share it.
    subject: str  # The trigger's entity or boundary, and its key: what tells such events apart.
    key: str
    verdict: Literal["passed", "violated", "inconclusive"]
    findings: tuple[Finding, ...] = ()


def edge(source: str | None, target: str) -> str:
    return f"{source or INITIAL} -> {target}"


def finding(verdict: FindingVerdict, subject: str, reason: str, *events: Event) -> Finding:
    return Finding(verdict=verdict, subject=subject, reason=reason, evidence=tuple(event.ref for event in events))

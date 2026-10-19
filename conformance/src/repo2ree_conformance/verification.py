"""The verification of one recording, as an artifact later steps read instead of verifying again.

``verify`` judges evidence once and keeps everything a view needs: the evidence it
judged, the rule results, each invariant occurrence's verdict, and the replayed
entities and exchanges. ``VerifiedModel`` reads it back with the shape views use, so
a view draws what was verified and can never reach a verdict of its own.

Events are referred to by their index in ``evidence.events``: references (``Event.ref``)
are human addresses that Git events of one commit share.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from repo2ree_conformance.check import CheckResult, Judgement, check, judge_occurrences, replay
from repo2ree_conformance.evidence import Event, Evidence, EvidenceModel
from repo2ree_conformance.spec import Spec

ARTIFACT = "verification.json"

__all__ = [
    "ARTIFACT",
    "Judgement",
    "Reach",
    "Verification",
    "VerifiedEntity",
    "VerifiedExchange",
    "VerifiedModel",
    "read_verification",
    "verify",
]


class VerifiedReach(EvidenceModel):
    source_state: str | None
    state: str
    event: int


class VerifiedInstance(EvidenceModel):
    partition: str | None
    current: str | None
    reached: tuple[VerifiedReach, ...]


class Verification(EvidenceModel):
    recording: str | None = None  # The recording directory it verified, when it verified one.
    result: CheckResult
    judgements: tuple[Judgement, ...]
    evidence: Evidence
    instances: dict[str, dict[str, VerifiedInstance]]
    exchanges: dict[str, dict[str, tuple[int, ...]]]  # Each exchange's events, in owner order.


def verify(spec: Spec, evidence: Evidence, recording: str | None = None) -> Verification:
    """Judge the evidence once; everything after reads the result."""
    result = check(spec, evidence)
    model, _, _ = replay(spec, evidence)
    index = {id(event): position for position, event in enumerate(evidence.events)}
    return Verification(
        recording=recording,
        result=result,
        judgements=tuple(judge_occurrences(model)),
        evidence=evidence,
        instances={
            entity: {
                key: VerifiedInstance(
                    partition=instance.partition,
                    current=instance.current,
                    reached=tuple(
                        VerifiedReach(source_state=item.source_state, state=item.state, event=index[id(item.event)])
                        for item in instance.reached
                    ),
                )
                for key, instance in by_key.items()
            }
            for entity, by_key in model.instances.items()
        },
        exchanges={
            boundary: {key: tuple(index[id(event)] for event in exchange.events) for key, exchange in by_key.items()}
            for boundary, by_key in model.exchanges.items()
        },
    )


def read_verification(path: Path) -> Verification:
    return Verification.model_validate_json(path.read_text())


# ================================================
# Read model: the verified evidence, shaped as views use it
# ================================================


@dataclass(frozen=True)
class Reach:
    source_state: str | None
    state: str
    event: Event


@dataclass(frozen=True)
class VerifiedEntity:
    partition: str | None
    current: str | None
    reached: tuple[Reach, ...]


@dataclass(frozen=True)
class VerifiedExchange:
    events: tuple[Event, ...]

    @property
    def request(self) -> Event | None:
        return next((event for event in self.events if event.kind == "send"), None)

    @property
    def outcome(self) -> Event | None:
        return next((event for event in self.events if event.kind in {"receive", "abandon"}), None)


@dataclass
class VerifiedModel:
    """What was verified, with events resolved: the evidence, entities, and exchanges views draw."""

    evidence: Evidence
    result: CheckResult
    judgements: tuple[Judgement, ...]
    instances: dict[str, dict[str, VerifiedEntity]] = field(default_factory=dict)
    exchanges: dict[str, dict[str, VerifiedExchange]] = field(default_factory=dict)

    @classmethod
    def of(cls, verification: Verification) -> VerifiedModel:
        events = verification.evidence.events
        return cls(
            evidence=verification.evidence,
            result=verification.result,
            judgements=verification.judgements,
            instances={
                entity: {
                    key: VerifiedEntity(
                        partition=instance.partition,
                        current=instance.current,
                        reached=tuple(Reach(r.source_state, r.state, events[r.event]) for r in instance.reached),
                    )
                    for key, instance in by_key.items()
                }
                for entity, by_key in verification.instances.items()
            },
            exchanges={
                boundary: {key: VerifiedExchange(tuple(events[i] for i in found)) for key, found in by_key.items()}
                for boundary, by_key in verification.exchanges.items()
            },
        )

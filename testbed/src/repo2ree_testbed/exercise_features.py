from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_testbed.exercise import Label
from repo2ree_testbed.exercise_cli import Ran, Replayed

type FeatureFamily = Literal["rule", "transition", "context", "outcome", "rule_outcome"]
FAMILIES: tuple[FeatureFamily, ...] = get_args(FeatureFamily.__value__)

type ActionStatus = Literal["succeeded", "failed", "canceled"]
type FailureCategory = Literal[
    "validation", "precondition", "conflict", "execution", "timeout", "unavailable", "internal"
]
type Store = Literal["ree", "review"]
type RuleVerdict = Literal["held", "violated", "inconclusive"]


class _Feature(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RuleTriggered(_Feature):
    family: Literal["rule"] = "rule"
    rule: str


class Transition(_Feature):
    family: Literal["transition"] = "transition"
    entity: str
    move: str


class InContext(_Feature):
    family: Literal["context"] = "context"
    entity: str
    move: str
    ree: Label | None = None
    store: Store


class Outcome(_Feature):
    family: Literal["outcome"] = "outcome"
    command: str
    ree: Label
    exit: int
    status: ActionStatus | None = None
    category: FailureCategory | None = None


class RuleOutcome(_Feature):
    family: Literal["rule_outcome"] = "rule_outcome"
    rule: str
    verdict: RuleVerdict


type Feature = Annotated[RuleTriggered | Transition | InContext | Outcome | RuleOutcome, Field(discriminator="family")]


def ordered(features: Iterable[Feature]) -> tuple[Feature, ...]:
    return tuple(sorted(set(features), key=lambda feature: feature.model_dump_json()))


def placed(partition: str) -> tuple[str | None, Store]:
    ree, _, within = partition.partition("/")
    return ree or None, "review" if within.startswith("reviews/") else "ree"


def _rule_verdicts(rule: dict[str, Any]) -> Iterator[RuleVerdict]:
    findings = rule["findings"]
    for verdict in ("violated", "inconclusive"):
        if any(finding["verdict"] == verdict for finding in findings):
            yield verdict
    if rule["triggered"] > len({finding["subject"] for finding in findings}):
        yield "held"


def from_report(report: dict[str, Any]) -> tuple[Feature, ...]:
    coverage = report["coverage"]
    triggered = [rule for rule in report["rules"] if rule["triggered"]]
    return ordered(
        [
            *(RuleTriggered(rule=rule["rule"]) for rule in triggered),
            *(
                Transition(entity=entity, move=move)
                for entity, counts in coverage["transitions"].items()
                for move, count in counts.items()
                if count
            ),
            *(
                InContext(entity=entity, move=move, ree=ree, store=store)
                for entity, partitions in coverage["partitions"].items()
                for partition, counts in partitions.items()
                for ree, store in (placed(partition),)
                for move, count in counts.items()
                if count
            ),
            *(
                RuleOutcome(rule=rule["rule"], verdict=verdict)
                for rule in triggered
                for verdict in _rule_verdicts(rule)
            ),
        ]
    )


def declared(report: dict[str, Any]) -> tuple[Feature, ...]:
    return ordered(
        [
            *(RuleTriggered(rule=rule["rule"]) for rule in report["rules"]),
            *(
                Transition(entity=entity, move=move)
                for entity, counts in report["coverage"]["transitions"].items()
                for move in counts
            ),
        ]
    )


def _outcome(ree: str, ran: Ran, command: Sequence[str]) -> Outcome:
    result = ran.result if isinstance(ran.result, dict) else {}
    status = result.get("status")
    failure = result.get("failure")
    category = failure.get("category") if isinstance(failure, dict) else None
    return Outcome.model_validate(
        {
            "command": " ".join(command),
            "ree": ree,
            "exit": ran.exit,
            "status": status if status in get_args(ActionStatus.__value__) else None,
            "category": category if category in get_args(FailureCategory.__value__) else None,
        }
    )


def outcomes(
    replayed: Sequence[Replayed], command_of: Callable[[Sequence[str]], dict[str, Any]]
) -> tuple[Feature, ...]:
    return ordered(
        _outcome(step.ree, ran, command_of(ran.words)["words"])
        for step in replayed
        for ran in (*step.prepared, *((step.ran,) if step.ran else ()))
    )

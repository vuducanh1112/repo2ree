from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_testbed.exercise_cli import Ran, Replayed

type BehaviourKind = Literal["verdict", "move", "outcome"]
type ActionStatus = Literal["succeeded", "failed", "canceled"]
type FailureCategory = Literal[
    "validation", "precondition", "conflict", "execution", "timeout", "unavailable", "internal"
]
type RuleVerdict = Literal["held", "violated", "inconclusive"]
type MachineKind = Literal["lifecycle", "field"]
MACHINE_KINDS: tuple[MachineKind, ...] = get_args(MachineKind.__value__)


class _Behaviour(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Verdict(_Behaviour):
    kind: Literal["verdict"] = "verdict"
    rule: str
    verdict: RuleVerdict


class Move(_Behaviour):
    kind: Literal["move"] = "move"
    aggregate: str
    machine: str
    part: MachineKind
    operation: str
    source: str
    target: str


class Outcome(_Behaviour):
    kind: Literal["outcome"] = "outcome"
    command: str
    status: ActionStatus | None = None
    category: FailureCategory | None = None


type Behaviour = Annotated[Verdict | Move | Outcome, Field(discriminator="kind")]


def ordered(behaviours: Iterable[Behaviour]) -> tuple[Behaviour, ...]:
    return tuple(sorted(set(behaviours), key=lambda behaviour: behaviour.model_dump_json()))


def _verdicts(rule: dict[str, Any]) -> Iterable[RuleVerdict]:
    findings = rule["findings"]
    for verdict in ("violated", "inconclusive"):
        if any(finding["verdict"] == verdict for finding in findings):
            yield verdict
    if rule["triggered"] > len({finding["subject"] for finding in findings}):
        yield "held"


def from_report(report: dict[str, Any]) -> tuple[Behaviour, ...]:
    return ordered(
        [
            *(
                Verdict(rule=rule["rule"], verdict=verdict)
                for rule in report["rules"]
                if rule["triggered"]
                for verdict in _verdicts(rule)
            ),
            *(
                Move(
                    aggregate=aggregate["aggregate"],
                    machine=move["machine"],
                    part=move["kind"],
                    operation=move["operation"],
                    source=move["source"],
                    target=move["target"],
                )
                for aggregate in report["aggregates"]
                for move in aggregate["moves"]
                if move["kind"] in MACHINE_KINDS and move["count"]
            ),
        ]
    )


def declared(spec: dict[str, Any]) -> tuple[Behaviour, ...]:
    core = spec["cli_core"]
    return ordered(
        [
            *(Verdict(rule=rule, verdict="held") for rule in core["rules"]),
            *(
                Move(
                    aggregate=name,
                    machine=machine["name"],
                    part=machine["kind"],
                    operation=operation,
                    source=edge["from"],
                    target=edge["to"],
                )
                for name, aggregate in spec["aggregates"].items()
                if name in core["entities"]
                for machine in aggregate["machines"]
                if machine["kind"] in MACHINE_KINDS
                for edge in machine["edges"]
                for operation in edge["by"]
            ),
        ]
    )


def _outcome(ran: Ran, command: Sequence[str]) -> Outcome:
    result = ran.result if isinstance(ran.result, dict) else {}
    status = result.get("status")
    failure = result.get("failure")
    category = failure.get("category") if isinstance(failure, dict) else None
    return Outcome.model_validate(
        {
            "command": " ".join(command),
            "status": status if status in get_args(ActionStatus.__value__) else None,
            "category": category if category in get_args(FailureCategory.__value__) else None,
        }
    )


def outcomes(
    replayed: Sequence[Replayed], command_of: Callable[[Sequence[str]], dict[str, Any]]
) -> tuple[Behaviour, ...]:
    return ordered(
        _outcome(ran, command_of(ran.words)["words"])
        for step in replayed
        for ran in (*step.prepared, *((step.ran,) if step.ran else ()))
    )

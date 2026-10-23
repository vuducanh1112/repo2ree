"""Recorded facts against the specification.

Whether they satisfy a condition, which ones a condition needs that a record lacks, and how they
disagree with their declarations.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import Any, Literal

from pydantic import JsonValue

from repo2ree_assurance_checker.spec.base import Condition, FactType


def matches(where: Condition, facts: dict[str, JsonValue], trigger: dict[str, JsonValue] | None = None) -> bool:
    """Absent facts never satisfy a condition, including a negated one; a fact recorded as null is absent.

    A ``{per, in}`` condition reads its key from ``trigger``'s facts: the trigger's, when the
    facts are another record's; the facts themselves otherwise.
    """
    for name, condition in where.items():
        if facts.get(name) is None:
            return False
        value = facts[name]
        if isinstance(condition, dict):
            if "per" in condition:
                key = (facts if trigger is None else trigger).get(str(condition["per"]))
                table = condition["in"]
                options = table.get(key) if isinstance(table, dict) and isinstance(key, str) else None
                if not isinstance(options, list) or value not in options:
                    return False
                continue
            if "not" in condition and value == condition["not"]:
                return False
            options = condition.get("in")
            if isinstance(options, list) and value not in options:
                return False
        elif value != condition:
            return False
    return True


def absent(where: Condition, facts: dict[str, JsonValue], trigger: dict[str, JsonValue] | None = None) -> list[str]:
    """The facts ``where`` needs that the records do not carry, so it cannot be decided either way."""
    missing = [name for name in where if facts.get(name) is None]
    for condition in where.values():
        if isinstance(condition, dict) and "per" in condition:
            key = str(condition["per"])
            if (facts if trigger is None else trigger).get(key) is None:
                missing.append(key)
    return missing


def fact_problems(
    declared: dict[str, FactType],
    required: Iterable[str],
    facts: dict[str, Any],
    allowed: Mapping[str, Collection[str]] | None = None,
) -> list[tuple[Literal["violated", "inconclusive"], str]]:
    """How a record's facts disagree with the vocabulary.

    Undeclared facts are the owner's own and never a problem. A declared fact of another
    type, or a value its declaration does not list, is violated: the owner gave a declared
    word another meaning. A required fact
    that is absent (or null) leaves the record short of what the rules need, so nothing
    it should have proven can be decided: inconclusive.
    """
    problems: list[tuple[Literal["violated", "inconclusive"], str]] = []
    for name, value in facts.items():
        kind = declared.get(name)
        if kind is None:
            continue
        if value is None:
            if not kind.endswith("?"):
                problems.append(("violated", f"fact {name!r} is null"))
            continue
        expected = {"str": str, "bool": bool, "int": int}[kind.rstrip("?")]
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            problems.append(("violated", f"fact {name!r} is not {kind}"))
        elif (options := (allowed or {}).get(name)) and value not in options:
            problems.append(("violated", f"fact {name!r} is {value!r}, which its declaration does not list"))
    if missing := sorted(name for name in required if facts.get(name) is None):
        problems.append(("inconclusive", f"missing required facts {missing}"))
    return problems


def declared_facts(declared: dict[str, FactType], facts: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """The facts the vocabulary declares; the rest are the owner's own and never judged."""
    return {name: value for name, value in facts.items() if name in declared}

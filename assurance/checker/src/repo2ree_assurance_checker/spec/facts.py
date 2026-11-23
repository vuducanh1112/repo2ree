from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import Any, Literal

from pydantic import JsonValue

from repo2ree_assurance_checker.spec.base import Condition, FactType


def matches(where: Condition, facts: dict[str, JsonValue], trigger: dict[str, JsonValue] | None = None) -> bool:
    for name, condition in where.items():
        if facts.get(name) is None:
            return False
        value = facts[name]
        if isinstance(condition, dict):
            if "has" in condition:
                needle = (facts if trigger is None else trigger).get(str(condition["has"]))
                if not isinstance(value, list) or needle is None or needle not in value:
                    return False
                continue
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
    missing = [name for name in where if facts.get(name) is None]
    for condition in where.values():
        if isinstance(condition, dict) and ("per" in condition or "has" in condition):
            key = str(condition.get("per", condition.get("has")))
            if (facts if trigger is None else trigger).get(key) is None:
                missing.append(key)
    return missing


def fact_problems(
    declared: dict[str, FactType],
    required: Iterable[str],
    facts: dict[str, Any],
    allowed: Mapping[str, Collection[str]] | None = None,
) -> list[tuple[Literal["violated", "inconclusive"], str]]:
    problems: list[tuple[Literal["violated", "inconclusive"], str]] = []
    for name, value in facts.items():
        kind = declared.get(name)
        if kind is None:
            continue
        if value is None:
            if not kind.endswith("?"):
                problems.append(("violated", f"fact {name!r} is null"))
            continue
        if kind == "[str]":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                problems.append(("violated", f"fact {name!r} is not {kind}"))
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
    return {name: value for name, value in facts.items() if name in declared}

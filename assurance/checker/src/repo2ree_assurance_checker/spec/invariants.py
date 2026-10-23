"""Cross-entity invariants: a trigger, what it requires, and how their conditions are spelled and checked."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Annotated, Any, Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from repo2ree_assurance_checker.spec.base import Condition, Name, SpecModel


class EntityTrigger(SpecModel):
    entity: Name
    to: tuple[Name, ...] = Field(min_length=1)
    source: tuple[str, ...] = Field(default=(), alias="from")
    where: Condition = Field(default_factory=dict)

    @field_validator("to", "source", mode="before")
    @classmethod
    def _states(cls, value: object) -> object:
        return cls.one_or_many(value)


class MessageTrigger(SpecModel):
    boundary: Name
    message: Name
    where: Condition = Field(default_factory=dict)


class EntityRequirement(SpecModel):
    """The keyed entity reached one of the states (with facts), optionally before the trigger."""

    entity: Name
    key_from: str
    reached: tuple[Name, ...] = Field(min_length=1)
    where: Condition = Field(default_factory=dict)
    order: Literal["any", "before"] = "any"

    @field_validator("reached", mode="before")
    @classmethod
    def _reached(cls, value: object) -> object:
        return (value,) if isinstance(value, str) else value


class MessageRequirement(SpecModel):
    boundary: Name
    message: Name
    key_from: str
    order: Literal["any", "before"] = "any"


class GuardRequirement(SpecModel):
    """The triggering transition's own facts satisfy a condition."""

    where: Condition = Field(min_length=1)


class ExclusionRequirement(SpecModel):
    """No instance of the entity in the trigger's partition is in these states at the trigger."""

    entity: Name
    in_states: tuple[Name, ...] = Field(min_length=1)


type Requirement = EntityRequirement | MessageRequirement | GuardRequirement | ExclusionRequirement


class Invariant(SpecModel):
    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*$")]
    pattern: Literal["requires", "response", "guard", "excludes"]
    summary: str
    when: EntityTrigger | MessageTrigger
    require: Requirement | None = None
    eventually: tuple[Name, ...] = ()

    @model_validator(mode="after")
    def pattern_fields(self) -> Self:
        expected: dict[str, tuple[type, ...]] = {
            "requires": (EntityRequirement, MessageRequirement),
            "guard": (GuardRequirement,),
            "excludes": (ExclusionRequirement,),
            "response": (type(None),),
        }
        if not isinstance(self.require, expected[self.pattern]):
            raise ValueError(f"{self.id}: '{self.pattern}' does not take this 'require'")
        if (self.pattern == "response") != bool(self.eventually):
            raise ValueError(f"{self.id}: only 'response' takes 'eventually'")
        if self.pattern in {"response", "guard", "excludes"} and not isinstance(self.when, EntityTrigger):
            raise ValueError(f"{self.id}: '{self.pattern}' takes an entity trigger")
        return self


def check_condition(
    owner: str,
    fact: str,
    condition: JsonValue,
    listed: Mapping[str, tuple[str, ...]],
    trigger_listed: Mapping[str, tuple[str, ...]],
    trigger_facts: Collection[str],
) -> None:
    """A condition's shape, and each value it names against the values its fact lists, where the fact lists them.

    ``{per = fact, in = {value = [values]}}`` takes its alternatives from the trigger's
    ``fact``: it gives a list for each value that fact lists, so none is left unsaid.
    """
    values = listed.get(fact)

    def named(items: list[JsonValue], context: str = "") -> None:
        if values is not None and (unknown := [item for item in items if item not in values]):
            raise ValueError(f"{owner}: {fact}{context} names values its declaration does not list: {unknown}")

    if isinstance(condition, dict):
        if set(condition) == {"per", "in"}:
            by, table = condition["per"], condition["in"]
            if not isinstance(by, str) or by not in trigger_facts:
                raise ValueError(f"{owner}: 'per' names {by!r}, which is not a trigger fact")
            if not isinstance(table, dict) or not all(isinstance(items, list) for items in table.values()):
                raise ValueError(f"{owner}: with 'per', 'in' takes a list of values for each value of {by}")
            keys = trigger_listed.get(by)
            if keys is None:
                raise ValueError(f"{owner}: 'per' needs {by} to list its values")
            if set(table) != set(keys):
                missing, extra = sorted(set(keys) - set(table)), sorted(set(table) - set(keys))
                raise ValueError(
                    f"{owner}: 'in' must give a list for each value of {by}: missing {missing}, unlisted {extra}"
                )
            for key, items in table.items():
                named(items, f" for {by} {key}")  # type: ignore[arg-type]
            return
        if len(condition) != 1 or next(iter(condition)) not in {"not", "in"}:
            raise ValueError(
                f"{owner}: a condition is a value, {{not = value}}, {{in = [values]}}, {{group = ...}}, "
                "or {per = fact, in = {value = [values]}}"
            )
        if "in" in condition:
            if not isinstance(condition["in"], list):
                raise ValueError(f"{owner}: 'in' takes a list")
            named(condition["in"])
        else:
            named([condition["not"]])
    elif isinstance(condition, list):
        raise ValueError(f"{owner}: use {{in = [values]}} for alternatives")
    else:
        named([condition])


type FactGroups = dict[str, dict[str, dict[str, tuple[str, ...]]]]


def spell_out_groups(invariant: dict[str, Any], groups: FactGroups) -> dict[str, Any]:
    """An invariant with each ``{ group = ... }`` condition replaced by ``{ in = [...] }`` over the groups' values.

    A group condition names one group or a list of them, of the fact as the condition's
    entity declares it: the trigger's, or the required entity's.
    """
    when, require = dict(invariant.get("when", {})), dict(invariant.get("require", {}))

    def spelled(entity: str | None, where: dict[str, Any]) -> dict[str, Any]:
        conditions = {}
        for fact, condition in where.items():
            if isinstance(condition, dict) and set(condition) == {"group"}:
                named = [condition["group"]] if isinstance(condition["group"], str) else list(condition["group"])
                declared = groups.get(entity or "", {}).get(fact, {})
                if unknown := [name for name in named if name not in declared]:
                    raise ValueError(f"{invariant.get('id')}: {entity}.{fact} declares no groups {unknown}")
                condition = {"in": [value for name in named for value in declared[name]]}
            conditions[fact] = condition
        return conditions

    if "where" in when:
        when["where"] = spelled(when.get("entity"), when["where"])
    if "where" in require:
        require["where"] = spelled(require.get("entity", when.get("entity")), require["where"])
    return invariant | {"when": when} | ({"require": require} if require else {})

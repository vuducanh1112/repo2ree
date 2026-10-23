"""What every part of the specification shares: its model base, names, fact types, and markers."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

type FactType = Literal["str", "str?", "bool", "bool?", "int", "int?"]
type Name = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")]
type Condition = dict[str, JsonValue]

# The only fact a requirement may name that is not a declared fact: the trigger's own key.
OWN_KEY = "$key"
# The source state of an entity's first transition, where a trigger may name it.
CREATED = "(none)"


class SpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @staticmethod
    def one_or_many(value: object) -> object:
        """A single name where a list is expected means a list of one."""
        return (value,) if isinstance(value, str) else value

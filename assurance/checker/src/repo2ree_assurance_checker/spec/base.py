from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

type FactType = Literal["str", "str?", "bool", "bool?", "int", "int?", "[str]"]
type Name = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")]
type Condition = dict[str, JsonValue]

OWN_KEY = "$key"
CREATED = "(none)"


class SpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @staticmethod
    def one_or_many(value: object) -> object:
        return (value,) if isinstance(value, str) else value

from __future__ import annotations

from typing import Any, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class StringValue(str):
    def __new__(cls, value: str) -> Self:
        text = cls.validate(str(value))
        return str.__new__(cls, text)

    @classmethod
    def validate(cls, value: str) -> str:
        if not value:
            raise ValueError(f"{cls.__name__} must not be empty")
        return value

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

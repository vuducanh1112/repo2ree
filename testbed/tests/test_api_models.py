"""The tiers' typed view of the API says only what the contract says."""

import json
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

import pytest
from pydantic import BaseModel

from repo2ree_testbed.api_models import CONTRACT_SCHEMAS
from repo2ree_testbed.artifacts import ROOT

SCHEMAS: dict[str, dict[str, Any]] = json.loads((ROOT / "contracts/openapi.json").read_text())["components"]["schemas"]
MODELS = sorted(CONTRACT_SCHEMAS.items(), key=lambda item: item[0].__name__)


def literals(annotation: object) -> set[object]:
    if get_origin(annotation) is Literal:
        return set(get_args(annotation))
    if get_origin(annotation) in {Union, UnionType}:
        return {value for member in get_args(annotation) for value in literals(member)}
    return set()


def enum_values(field: dict[str, Any]) -> set[object]:
    if "$ref" in field:
        return enum_values(SCHEMAS[field["$ref"].rsplit("/", 1)[-1]])
    found = set(field.get("enum", ()))
    for member in field.get("anyOf", ()):
        found |= enum_values(member)
    return found


@pytest.mark.parametrize(("model", "schema"), MODELS, ids=lambda value: getattr(value, "__name__", value))
def test_a_models_fields_are_the_contracts(model: type[BaseModel], schema: str) -> None:
    assert set(model.model_fields) <= set(SCHEMAS[schema]["properties"])


@pytest.mark.parametrize(("model", "schema"), MODELS, ids=lambda value: getattr(value, "__name__", value))
def test_a_models_closed_vocabularies_are_the_contracts(model: type[BaseModel], schema: str) -> None:
    for name, field in model.model_fields.items():
        if values := literals(field.annotation):
            assert values == enum_values(SCHEMAS[schema]["properties"][name]), name

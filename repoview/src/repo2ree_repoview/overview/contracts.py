"""The published contracts the overview lists: the environment variables and the HTTP API."""

from __future__ import annotations

from pydantic import Field, JsonValue

from repo2ree_repoview.documents import Document
from repo2ree_repoview.repository import ROOT

ENVIRONMENT = ROOT / "contracts/config/environment.json"
OPENAPI = ROOT / "contracts/openapi.json"


class _Schema(Document):
    default: JsonValue = None


class Variable(Document):
    owner: str = ""
    kind: str = ""
    value_schema: _Schema = Field(default=_Schema(), alias="schema")


class Environment(Document):
    variables: dict[str, Variable]
    patterns: dict[str, Variable] = Field(default_factory=dict)

    @classmethod
    def read(cls) -> Environment:
        return cls.model_validate_json(ENVIRONMENT.read_bytes())


class Operation(Document):
    tags: tuple[str, ...] = ()
    summary: str = ""


class OpenApi(Document):
    paths: dict[str, dict[str, Operation]]

    @classmethod
    def read(cls) -> OpenApi:
        return cls.model_validate_json(OPENAPI.read_bytes())

    @property
    def operations(self) -> int:
        return sum(len(methods) for methods in self.paths.values())

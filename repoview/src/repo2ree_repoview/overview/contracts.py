"""The published contracts the overview reads: the command line, the HTTP API, and the environment variables."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from repo2ree_repoview.documents import Document
from repo2ree_repoview.repository import ROOT

CONTRACTS = ROOT / "contracts"
ENVIRONMENT = CONTRACTS / "config/environment.json"
OPENAPI = CONTRACTS / "openapi.json"
CLI = CONTRACTS / "cli/cli.schema.json"
HTTP_METHODS = ("get", "post", "put", "patch", "delete")


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


# ================================================
# The HTTP API
# ================================================


class _Media(Document):
    media_schema: dict[str, JsonValue] = Field(default_factory=dict, alias="schema")


class _Body(Document):
    content: dict[str, _Media] = Field(default_factory=dict)


class Operation(Document):
    operation_id: str = Field(default="", alias="operationId")
    tags: tuple[str, ...] = ()
    summary: str = ""
    request_body: _Body | None = Field(default=None, alias="requestBody")
    responses: dict[str, _Body] = Field(default_factory=dict)
    # Where the API's contract says which operations advance each authoring step.
    step_actions: dict[str, list[str]] = Field(default_factory=dict, alias="x-repo2ree-step-actions")

    @property
    def request(self) -> str:
        return shape(self.request_body)

    @property
    def response(self) -> str:
        """What the first successful response answers with."""
        status = next((code for code in sorted(self.responses) if code.startswith("2")), None)
        return shape(self.responses[status]) if status else ""


class OpenApi(Document):
    paths: dict[str, dict[str, Operation]]

    @classmethod
    def read(cls) -> OpenApi:
        return cls.model_validate_json(OPENAPI.read_bytes())

    @property
    def operations(self) -> int:
        return sum(1 for _ in self.each())

    def each(self) -> list[tuple[str, str, Operation]]:
        return [
            (path, method, operation)
            for path, methods in self.paths.items()
            for method, operation in methods.items()
            if method in HTTP_METHODS
        ]

    @property
    def step_actions(self) -> dict[str, list[str]]:
        """The operations that advance each authoring step, as the contract says."""
        return next((operation.step_actions for _, _, operation in self.each() if operation.step_actions), {})


def shape(body: _Body | None) -> str:
    """What a request or response body carries: its schema's name, ``bytes``, or nothing."""
    if body is None or not body.content:
        return ""
    media, carried = next(iter(body.content.items()))
    if media != "application/json":
        return "bytes" if "octet-stream" in media or "zip" in media else media
    return schema_name(carried.media_schema)


def schema_name(schema: dict[str, JsonValue] | JsonValue) -> str:
    """A schema as the reader names it: its model, a union of them, a list of one, or its type."""
    if not isinstance(schema, dict):
        return ""
    if isinstance(ref := schema.get("$ref"), str):
        return ref.rsplit("/", 1)[-1]
    for union in ("anyOf", "oneOf"):
        if isinstance(members := schema.get(union), list):
            return " | ".join(name for name in (schema_name(member) for member in members) if name)
    if schema.get("type") == "array":
        return f"list[{schema_name(schema.get('items'))}]"
    kind = schema.get("type")
    return kind if isinstance(kind, str) else ""


# ================================================
# The command line
# ================================================


class CliParam(Document):
    name: str
    kind: Literal["option", "argument"]
    required: bool = False
    multiple: bool = False
    flag: bool = False
    negation: str | None = None
    type: str = ""
    choices: tuple[str, ...] = ()
    help: str = ""


class CliStdin(Document):
    field: str
    format: Literal["text", "json"]
    description: str = ""


class CliCommand(Document):
    words: tuple[str, ...]
    summary: str = ""
    runs: bool = False
    operations: tuple[str, ...] = ()
    params: tuple[CliParam, ...] = ()
    stdin: CliStdin | None = None
    stdout: Literal["result", "bytes", "script", "schema"] = "result"
    outputs: dict[str, JsonValue] | None = None


class CliStep(Document):
    key: str
    order: int
    label: str
    requires: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()


class CliSchema(Document):
    exit_codes: dict[str, str]
    failure_categories: tuple[str, ...]
    events: dict[str, str]
    steps: tuple[CliStep, ...]
    commands: tuple[CliCommand, ...]

    @classmethod
    def read(cls) -> CliSchema:
        return cls.model_validate_json(CLI.read_bytes())

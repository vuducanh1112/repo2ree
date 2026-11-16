"""A command's arguments as Click parameters, generated from its model, and the model read back from them.

The spelling is the one ``repo2ree_protocol.argv`` writes, so what a workbench runs (``to_argv``) is what a person
types, and a person gets help, choices, ``--opt=value`` and completion for it.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any, Literal, Union, cast, get_args, get_origin

import click
from click.shell_completion import CompletionItem
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

from repo2ree_protocol.argv import (
    TARGET_OPTION,
    Positional,
    Stdin,
    Verb,
    is_model,
    is_target,
    item_of,
    marked,
    option_name,
)
from repo2ree_protocol.command import ScriptTargetSelectorArg, TargetKind

KINDS: tuple[str, ...] = get_args(TargetKind)
_EXPERIMENT_KINDS = ("experiment_run", "experiment_verify")
# Nested options join their model's field and their own with this, where Click wants an identifier.
_NESTED = "__"


class TargetType(click.ParamType):
    """A script target, ``KIND`` or ``KIND:EXPERIMENT``."""

    name = "KIND[:EXPERIMENT]"

    def convert(self, value: Any, param: click.Parameter | None, ctx: click.Context | None) -> ScriptTargetSelectorArg:
        if isinstance(value, ScriptTargetSelectorArg):
            return value
        kind, colon, experiment = str(value).partition(":")
        if kind not in KINDS:
            self.fail(f"{kind!r} is no script kind; one of {', '.join(KINDS)}", param, ctx)
        try:
            return ScriptTargetSelectorArg.model_validate(
                {"kind": kind, "experiment_name": experiment if colon else None}
            )
        except ValidationError as exc:
            self.fail(_first_error(exc), param, ctx)

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
        words = [f"{kind}:" if kind in _EXPERIMENT_KINDS else kind for kind in KINDS]
        return [CompletionItem(word) for word in words if word.startswith(incomplete)]


TARGET = TargetType()


@dataclass(frozen=True)
class Spelling:
    """How a model's fields are spelled as Click parameters.

    ``optional`` names required fields the command line fills itself when they are not given; ``hidden`` names
    fields a workbench passes and a person does not.
    """

    model: type[BaseModel]
    optional: Collection[str] = ()
    hidden: Collection[str] = ()
    params: list[click.Parameter] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", self._params())

    @property
    def stdin_field(self) -> tuple[str, FieldInfo] | None:
        return next(((name, info) for name, info in self.model.model_fields.items() if marked(info, Stdin)), None)

    def build(self, params: dict[str, Any], stdin: bytes | None, **filled: Any) -> BaseModel:
        """The model the parsed ``params`` and ``stdin`` spell, with ``filled`` for fields not given."""
        values: dict[str, Any] = {}
        for name, info in self.model.model_fields.items():
            if marked(info, Verb):
                continue
            if marked(info, Stdin):
                values[name] = _from_stdin(name, info, stdin)
            elif is_model(info.annotation):
                nested = cast(type[BaseModel], info.annotation).model_fields
                given = {inner: params.get(f"{name}{_NESTED}{inner}") for inner in nested}
                given = {inner: value for inner, value in given.items() if value not in (None, ())}
                if given:
                    values[name] = given
            else:
                value = params.get(name)
                if item_of(info.annotation) is not None:
                    value = list(value or ())
                    if value or info.is_required():
                        values[name] = value
                elif value is not None:
                    values[name] = value
        values = {**{name: value for name, value in filled.items() if name not in values}, **values}
        try:
            return self.model.model_validate(values)
        except ValidationError as exc:
            raise click.UsageError(_first_error(exc)) from exc

    def _params(self) -> list[click.Parameter]:
        options: list[click.Parameter] = []
        arguments: list[click.Parameter] = []
        for name, info in self.model.model_fields.items():
            if marked(info, Verb) or marked(info, Stdin):
                continue
            if marked(info, Positional):
                arguments.append(click.Argument([name], type=_type(info.annotation), required=info.is_required()))
            elif is_model(info.annotation):
                nested = cast(type[BaseModel], info.annotation).model_fields
                options += [
                    self._option(f"{name}.{inner}", f"{name}{_NESTED}{inner}", inner_info, required=False)
                    for inner, inner_info in nested.items()
                ]
            else:
                required = info.is_required() and name not in self.optional
                options.append(self._option(name, name, info, required=required))
        return [*options, *arguments]

    def _option(self, spelled: str, dest: str, info: FieldInfo, *, required: bool) -> click.Option:
        annotation = info.annotation
        hidden = spelled in self.hidden
        help_text = info.description
        item = item_of(annotation)
        if item is not None and is_target(item):
            return click.Option([TARGET_OPTION, dest], type=TARGET, multiple=True, help=help_text, hidden=hidden)
        if annotation is bool:
            flag = option_name(spelled)
            default = info.get_default(call_default_factory=True)
            return click.Option(
                [f"{flag}/--no-{flag[2:]}", dest], default=default, show_default=True, help=help_text, hidden=hidden
            )
        default = info.get_default(call_default_factory=True) if not info.is_required() else None
        return click.Option(
            [option_name(spelled), dest],
            type=_type(item if item is not None else annotation),
            multiple=item is not None,
            required=required,
            default=None,
            help=help_text + (f"  [default: {default}]" if default not in (None, "", (), []) else "")
            if help_text
            else None,
            hidden=hidden,
        )


def reads_stdin(model: type[BaseModel]) -> bool:
    """Whether a command of these arguments reads one of them on stdin."""
    return any(marked(info, Stdin) for info in model.model_fields.values())


def read_stdin(model: type[BaseModel]) -> bytes | None:
    """What the command reads on stdin; refused at a terminal, where it would wait on what the person types."""
    if not reads_stdin(model):
        return None
    if sys.stdin.isatty():
        name = next(name for name, info in model.model_fields.items() if marked(info, Stdin))
        raise click.UsageError(f"{name} is read from stdin: pipe it in, as in `… < FILE`")
    return click.get_binary_stream("stdin").read()


def _from_stdin(name: str, info: FieldInfo, stdin: bytes | None) -> Any:
    if stdin is None:
        raise click.UsageError(f"{name} is read from stdin, and there is none")
    if info.annotation is str:
        return stdin.decode()
    try:
        return json.loads(stdin)
    except ValueError as exc:
        raise click.UsageError(f"{name} on stdin is not JSON: {exc}") from exc


def _type(annotation: Any) -> click.ParamType:
    origin = get_origin(annotation)
    if origin is Literal:
        return click.Choice([str(value) for value in get_args(annotation)])
    if origin in (Union, type(int | None)):
        inner = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(inner) == 1:
            return _type(inner[0])
    if annotation is int:
        return click.INT
    return click.STRING


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(part) for part in error["loc"])
    return f"{where}: {error['msg']}" if where else str(error["msg"])

"""How a command's arguments are spelled on the command line, read off their models.

A field's spelling follows from its type and its markers:

* ``Verb``: the field names the command, which its verb spells, so it is no option;
* ``Positional``: a positional argument, in field order;
* ``Stdin``: what is read on stdin, text as it is and anything else as JSON;
* ``bool``: a flag, ``--again`` for true and ``--no-again`` for false;
* a model (``ReviewLaunch``): its own fields as dotted options, ``--launch.mode native``;
* a list of script targets: ``--target kind`` or ``--target kind:experiment``, once per target;
* a list or tuple of anything else: its option once per element;
* anything else: ``--field-name value``.

An option is written only when its value is not the field's default, so an argv says what was asked and nothing
more. Positionals come last, after ``--``, so one that starts with ``-`` is still a positional. ``ree`` reads these
spellings back with options generated from the same models (``repo2ree_cli.options``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo


@dataclass(frozen=True)
class Verb:
    """The field names the command: the verb spells it."""


@dataclass(frozen=True)
class Positional:
    """The field is a positional argument."""


@dataclass(frozen=True)
class Stdin:
    """The field is read from stdin."""


VERB = Verb()
POSITIONAL = Positional()
STDIN = Stdin()
TARGET_OPTION = "--target"


def encode_args(args: BaseModel) -> tuple[list[str], bytes | None]:
    """The words after the verb, and the stdin, that spell ``args``."""
    options: list[str] = []
    positionals: list[str] = []
    stdin: bytes | None = None
    for name, info in type(args).model_fields.items():
        value = getattr(args, name)
        if marked(info, Verb):
            continue
        if marked(info, Positional):
            positionals.append(str(value))
        elif marked(info, Stdin):
            stdin = value.encode() if isinstance(value, str) else json.dumps(value).encode()
        elif value != info.get_default(call_default_factory=True):
            options += _encode_option(name, info.annotation, value)
    return ([*options, "--", *positionals] if positionals else options), stdin


def option_name(name: str) -> str:
    """The option that spells the field ``name``: ``--again``, ``--launch.mode``."""
    return "--" + name.replace("_", "-")


def target_word(target: BaseModel) -> str:
    """A script target as one word: ``kind`` or ``kind:experiment``."""
    kind, experiment = target.model_dump()["kind"], target.model_dump()["experiment_name"]
    return f"{kind}:{experiment}" if experiment is not None else str(kind)


def marked(info: FieldInfo, marker: type) -> bool:
    return any(isinstance(item, marker) for item in info.metadata)


def is_model(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def is_target(annotation: Any) -> bool:
    return is_model(annotation) and set(annotation.model_fields) == {"kind", "experiment_name"}


def item_of(annotation: Any) -> Any | None:
    """What a list or tuple annotation holds; None for anything else."""
    if get_origin(annotation) in (list, tuple):
        return next((arg for arg in get_args(annotation) if arg is not Ellipsis), None)
    return None


def _encode_option(name: str, annotation: Any, value: Any) -> list[str]:
    option = option_name(name)
    if annotation is bool:
        return [option] if value else ["--no-" + option[2:]]
    if is_model(annotation):
        words: list[str] = []
        for field, info in annotation.model_fields.items():
            inner = getattr(value, field)
            if inner != info.get_default(call_default_factory=True):
                words += _encode_option(f"{name}.{field}", info.annotation, inner)
        return words
    item = item_of(annotation)
    if item is not None and is_target(item):
        return [word for target in value for word in (TARGET_OPTION, target_word(target))]
    if item is not None:
        return [word for element in value for word in (option, str(element))]
    return [option, str(value)]

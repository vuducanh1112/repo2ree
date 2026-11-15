"""How a command's arguments are spelled on the command line, read off their models.

A field's spelling follows from its type and its markers:

* ``Positional``: a positional argument, in field order;
* ``Stdin``: what is read on stdin, text as it is and anything else as JSON;
* ``bool``: a flag, ``--prune-workspace`` for true and ``--no-prune-workspace`` for false;
* a model (``ReviewLaunch``): its own fields as dotted options, ``--launch.mode native``;
* a list of script targets: ``--target kind`` or ``--target kind:experiment``, once per target;
* a list or tuple of anything else: its option once per element;
* anything else: ``--field-name value``.

An option is written only when its value is not the field's default, so an argv says what was asked and nothing
more. Positionals come last, after ``--``, so one that starts with ``-`` is still a positional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo


@dataclass(frozen=True)
class Positional:
    """The field is a positional argument."""


@dataclass(frozen=True)
class Stdin:
    """The field is read from stdin."""


POSITIONAL = Positional()
STDIN = Stdin()
TARGET_OPTION = "--target"


class ArgvError(ValueError):
    """Words that spell no command: an unknown verb, a missing argument, or an option the command does not take."""


def reads_stdin(model: type[BaseModel]) -> bool:
    """Whether a command of these arguments reads one of them on stdin."""
    return any(_marked(info, Stdin) for info in model.model_fields.values())


def describe_args(model: type[BaseModel]) -> list[str]:
    """How each argument of ``model`` is spelled, one line each, for a command's help."""
    lines = []
    for name, info in model.model_fields.items():
        if _marked(info, Positional):
            lines.append(name.upper())
        elif _marked(info, Stdin):
            lines.append(f"{name} on stdin" + ("" if info.annotation is str else ", as JSON"))
        elif _is_target(_item(info.annotation)):
            lines.append(f"{TARGET_OPTION} KIND[:EXPERIMENT], repeated")
        elif _is_model(info.annotation):
            nested = cast(type[BaseModel], info.annotation).model_fields
            lines += [f"--{name.replace('_', '-')}.{field.replace('_', '-')} VALUE" for field in nested]
        elif info.annotation is bool:
            lines.append("--" + name.replace("_", "-"))
        else:
            lines.append(f"--{name.replace('_', '-')} VALUE" + (", repeated" if _item(info.annotation) else ""))
    return lines


def encode_args(args: BaseModel) -> tuple[list[str], bytes | None]:
    """The words after the verb, and the stdin, that spell ``args``."""
    options: list[str] = []
    positionals: list[str] = []
    stdin: bytes | None = None
    for name, info in type(args).model_fields.items():
        value = getattr(args, name)
        if _marked(info, Positional):
            positionals.append(str(value))
        elif _marked(info, Stdin):
            stdin = value.encode() if isinstance(value, str) else json.dumps(value).encode()
        elif value != info.get_default(call_default_factory=True):
            options += _encode_option(name, info.annotation, value)
    return ([*options, "--", *positionals] if positionals else options), stdin


def decode_args(model: type[BaseModel], words: list[str], stdin: bytes | None) -> BaseModel:
    """Read the words after the verb, and the stdin, back into ``model``."""
    fields = model.model_fields
    values: dict[str, Any] = {}
    positionals: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        index += 1
        if word == "--":
            positionals += words[index:]
            break
        if not word.startswith("--"):
            positionals.append(word)
            continue
        if word == TARGET_OPTION and (field := _target_field(model)) is not None:
            kind, colon, experiment = _value(words, index, word).partition(":")
            values.setdefault(field, []).append({"kind": kind, "experiment_name": experiment if colon else None})
            index += 1
            continue
        head, _, nested = word[2:].replace("-", "_").partition(".")
        if not nested and head.startswith("no_") and _is_flag(fields.get(head[3:])):
            values[head[3:]] = False
            continue
        info = fields.get(head)
        if info is None or _marked(info, Positional) or _marked(info, Stdin):
            raise ArgvError(f"{model.__name__} takes no option {word}")
        if not nested and _is_flag(info):
            values[head] = True
            continue
        value = _value(words, index, word)
        index += 1
        if nested:
            inner = (
                cast(type[BaseModel], info.annotation).model_fields.get(nested) if _is_model(info.annotation) else None
            )
            if inner is None:
                raise ArgvError(f"{model.__name__} takes no option {word}")
            _store(values.setdefault(head, {}), nested, inner, value)
        else:
            _store(values, head, info, value)
    expected = [name for name, info in fields.items() if _marked(info, Positional)]
    if len(positionals) != len(expected):
        raise ArgvError(f"expected {len(expected)} argument(s) ({' '.join(expected)}), got {len(positionals)}")
    values.update(zip(expected, positionals, strict=True))
    for name, info in fields.items():
        # A list written as no options at all is an empty one.
        if name not in values and _item(info.annotation) is not None and info.is_required():
            values[name] = []
        if _marked(info, Stdin):
            if stdin is None:
                raise ArgvError(f"{name} is read from stdin, and there is none")
            values[name] = stdin.decode() if info.annotation is str else json.loads(stdin)
    return model.model_validate(values)


def _encode_option(name: str, annotation: Any, value: Any) -> list[str]:
    option = "--" + name.replace("_", "-")
    if annotation is bool:
        return [option] if value else ["--no-" + option[2:]]
    if _is_model(annotation):
        words: list[str] = []
        for field, info in annotation.model_fields.items():
            inner = getattr(value, field)
            if inner != info.get_default(call_default_factory=True):
                words += _encode_option(f"{name}.{field}", info.annotation, inner)
        return words
    item = _item(annotation)
    if item is not None and _is_target(item):
        return [word for target in value for word in (TARGET_OPTION, _target(target))]
    if item is not None:
        return [word for element in value for word in (option, str(element))]
    return [option, str(value)]


def _store(values: dict[str, Any], name: str, info: FieldInfo, value: str) -> None:
    if _item(info.annotation) is not None:
        values.setdefault(name, []).append(value)
    else:
        values[name] = value


def _value(words: list[str], index: int, option: str) -> str:
    if index >= len(words):
        raise ArgvError(f"{option} needs a value")
    return words[index]


def _target(target: BaseModel) -> str:
    kind, experiment = target.model_dump()["kind"], target.model_dump()["experiment_name"]
    return f"{kind}:{experiment}" if experiment is not None else str(kind)


def _target_field(model: type[BaseModel]) -> str | None:
    return next((name for name, info in model.model_fields.items() if _is_target(_item(info.annotation))), None)


def _marked(info: FieldInfo, marker: type) -> bool:
    return any(isinstance(item, marker) for item in info.metadata)


def _is_flag(info: FieldInfo | None) -> bool:
    return info is not None and info.annotation is bool


def _is_model(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _is_target(annotation: Any) -> bool:
    return _is_model(annotation) and set(annotation.model_fields) == {"kind", "experiment_name"}


def _item(annotation: Any) -> Any | None:
    if get_origin(annotation) in (list, tuple):
        return next((arg for arg in get_args(annotation) if arg is not Ellipsis), None)
    return None

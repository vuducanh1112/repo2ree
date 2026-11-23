from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo


@dataclass(frozen=True)
class Verb:
    pass


@dataclass(frozen=True)
class Positional:
    pass


@dataclass(frozen=True)
class Stdin:
    pass


VERB = Verb()
POSITIONAL = Positional()
STDIN = Stdin()
TARGET_OPTION = "--target"


def encode_args(args: BaseModel) -> tuple[list[str], bytes | None]:
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
    return "--" + name.replace("_", "-")


def target_word(target: BaseModel) -> str:
    kind, experiment = target.model_dump()["kind"], target.model_dump()["experiment_name"]
    return f"{kind}:{experiment}" if experiment is not None else str(kind)


def marked(info: FieldInfo, marker: type) -> bool:
    return any(isinstance(item, marker) for item in info.metadata)


def is_model(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def is_target(annotation: Any) -> bool:
    return is_model(annotation) and set(annotation.model_fields) == {"kind", "experiment_name"}


def item_of(annotation: Any) -> Any | None:
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

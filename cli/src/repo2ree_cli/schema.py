from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, get_args

import click
from pydantic import TypeAdapter

from repo2ree_cli.options import TARGET, Spelling
from repo2ree_protocol.catalog import ReeStep
from repo2ree_protocol.result import ActionResult, FailureCategory

Stdout = Literal["result", "bytes", "script", "schema"]
_RESULT = "result"


class ReeCommand(click.Command):
    def __init__(
        self,
        *args: Any,
        words: Sequence[str] = (),
        outputs: Any = None,
        spelling: Spelling | None = None,
        runs: bool = False,
        operations: Sequence[str] = (),
        stdout: Stdout = "result",
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.words = tuple(words)
        self.outputs = outputs
        self.spelling = spelling
        self.runs = runs
        self.operations = tuple(operations)
        self.stdout: Stdout = stdout


_EVENTS = {
    "started": "A command began a run: run_id, operation. Cancel it with `ree cancel RUN_ID`.",
    "log": "A line of the run's log: stream (system, stdout, stderr), level, message.",
    "span": "A trace span, when the workbench asks for them.",
}


def describe(
    group: click.Group, words: Sequence[str], exit_codes: Mapping[int, str], steps: Sequence[ReeStep]
) -> dict[str, Any]:
    commands = _commands(group, ())
    if words:
        commands = [command for command in commands if command.words == tuple(words)]
        if not commands:
            raise LookupError(f"no command {' '.join(words)!r}")
    adapters: list[tuple[str, Literal["validation"], TypeAdapter[Any]]] = [
        (_RESULT, "validation", TypeAdapter(ActionResult))
    ]
    adapters += [
        (" ".join(command.words), "validation", TypeAdapter(command.outputs))
        for command in commands
        if command.outputs is not None
    ]
    schemas, definitions = TypeAdapter.json_schemas(adapters)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:repo2ree:cli",
        "exit_codes": {str(code): meaning for code, meaning in exit_codes.items()},
        "failure_categories": list(get_args(FailureCategory)),
        "result": schemas[(_RESULT, "validation")],
        "events": _EVENTS,
        "steps": [
            {
                "key": step.key,
                "order": step.order,
                "label": step.label,
                "requires": step.requires,
                "commands": step.commands,
            }
            for step in steps
        ],
        "commands": [_command(command, schemas.get((" ".join(command.words), "validation"))) for command in commands],
        "$defs": definitions.get("$defs", {}),
    }


def _commands(group: click.Group, prefix: tuple[str, ...]) -> list[ReeCommand]:
    found: list[ReeCommand] = []
    for name in sorted(group.commands):
        command = group.commands[name]
        if command.hidden:
            continue
        if isinstance(command, click.Group):
            found += _commands(command, (*prefix, name))
        elif isinstance(command, ReeCommand):
            found.append(command)
        else:
            raise TypeError(f"{' '.join((*prefix, name))} is no ReeCommand: give it its words and outputs")
    return found


def _command(command: ReeCommand, outputs: Any) -> dict[str, Any]:
    return {
        "words": list(command.words),
        "summary": command.get_short_help_str(limit=200),
        "help": command.help or "",
        "runs": command.runs,
        "operations": list(command.operations),
        "params": [_param(param) for param in command.params if not getattr(param, "hidden", False)],
        "stdin": _stdin(command.spelling) if command.spelling else None,
        "stdout": command.stdout,
        "outputs": outputs,
    }


def _param(param: click.Parameter) -> dict[str, Any]:
    described: dict[str, Any] = {
        "name": param.opts[0] if isinstance(param, click.Option) else (param.name or ""),
        "kind": "option" if isinstance(param, click.Option) else "argument",
        "required": param.required,
        "multiple": param.multiple,
    }
    if isinstance(param, click.Option):
        described["help"] = param.help or ""
        if param.is_flag:
            described["flag"] = True
            described["default"] = param.default
            if param.secondary_opts:
                described["negation"] = param.secondary_opts[0]
    if isinstance(param.type, click.Choice):
        described["choices"] = list(param.type.choices)
    elif param.type is TARGET:
        described["type"] = TARGET.name
        described["choices"] = [item.value for item in TARGET.shell_complete(None, param, "")]  # type: ignore[arg-type]
    elif not (isinstance(param, click.Option) and param.is_flag):
        described["type"] = param.type.name
    return described


def _stdin(spelling: Spelling) -> dict[str, Any] | None:
    found = spelling.stdin_field
    if found is None:
        return None
    name, info = found
    return {
        "field": name,
        "format": "text" if info.annotation is str else "json",
        "description": info.description or "",
    }

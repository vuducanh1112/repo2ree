"""``ree schema``: every command as data, read off the command line itself, for an agent to learn ``ree`` by.

Each command says the words that run it, its options and arguments, what it reads on stdin, what it prints (one
result, bytes, or a script) and the model of its result's outputs. The exit statuses, the failure categories and the
result and event shapes come with them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, get_args

import click
from pydantic import TypeAdapter

from repo2ree_cli.options import TARGET, Spelling
from repo2ree_protocol.result import ActionResult, FailureCategory

Stdout = Literal["result", "bytes", "script", "schema"]


class ReeCommand(click.Command):
    """A command and what an agent is told of it: its words, the model of its outputs, and what it prints."""

    def __init__(
        self,
        *args: Any,
        words: Sequence[str] = (),
        outputs: Any = None,
        spelling: Spelling | None = None,
        runs: bool = False,
        stdout: Stdout = "result",
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.words = tuple(words)
        self.outputs = outputs
        self.spelling = spelling
        self.runs = runs
        self.stdout: Stdout = stdout


_EVENTS = {
    "started": "A command began a run: run_id, operation. Cancel it with `ree cancel RUN_ID`.",
    "log": "A line of the run's log: stream (system, stdout, stderr), level, message.",
    "span": "A trace span, when the workbench asks for them.",
}


def describe(group: click.Group, words: Sequence[str], exit_codes: Mapping[int, str]) -> dict[str, Any]:
    """Every command of ``group``, or the one ``words`` names, with what is common to them all."""
    commands = list(_commands(group, ()))
    if words:
        matching = [entry for entry in commands if entry["words"] == list(words)]
        if not matching:
            raise LookupError(f"no command {' '.join(words)!r}")
        commands = matching
    return {
        "exit_codes": {str(code): meaning for code, meaning in exit_codes.items()},
        "failure_categories": list(get_args(FailureCategory)),
        "result": ActionResult.model_json_schema(),
        "events": _EVENTS,
        "commands": commands,
    }


def _commands(group: click.Group, prefix: tuple[str, ...]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name in sorted(group.commands):
        command = group.commands[name]
        if command.hidden:
            continue
        if isinstance(command, click.Group):
            entries += _commands(command, (*prefix, name))
        else:
            entries.append(_command(command, (*prefix, name)))
    return entries


def _command(command: click.Command, words: tuple[str, ...]) -> dict[str, Any]:
    ree = command if isinstance(command, ReeCommand) else None
    entry: dict[str, Any] = {
        "words": list(words),
        "summary": command.get_short_help_str(limit=200),
        "help": command.help or "",
        "runs": bool(ree and ree.runs),
        "params": [_param(param) for param in command.params if not getattr(param, "hidden", False)],
        "stdin": _stdin(ree.spelling) if ree and ree.spelling else None,
        "stdout": ree.stdout if ree else "result",
        "outputs": TypeAdapter(ree.outputs).json_schema() if ree and ree.outputs is not None else None,
    }
    return entry


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

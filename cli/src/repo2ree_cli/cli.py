"""``ree``: every command on an REE, for a person at a terminal and for a workbench alike.

Each command is a verb (``repo2ree_protocol.verbs``) run through core's session against the REE at ``-C`` or,
without it, the nearest one above the current directory. A person reads the run as plain lines; ``--json`` is the
machine form a workbench reads: NDJSON log events on stderr and the result as one JSON line on stdout.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, get_args
from uuid import uuid4

import click
from pydantic import BaseModel, ValidationError

from repo2ree_authoring.lint import CONTRACT_ONLY, lint_script
from repo2ree_authoring.targets import resolve_target
from repo2ree_authoring.templates import script_template_catalog
from repo2ree_core.bundle.download import materialized_ree_download
from repo2ree_core.doctor import run_doctor
from repo2ree_core.evidence.review.store import load_reviews
from repo2ree_core.execution.runners import runner_from_environment
from repo2ree_core.operations.capture import settle_interrupted
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.read_models.files import read_ree_file_bytes
from repo2ree_core.operations.read_models.ree_document import get_ree_document, get_ree_steps
from repo2ree_core.operations.session import request_cancel, run_session
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_protocol.argv import ArgvError, describe_args, reads_stdin
from repo2ree_protocol.build import current_build
from repo2ree_protocol.catalog import ReeSteps
from repo2ree_protocol.command import (
    AcquireSourceCommand,
    LoadReeBundleCommand,
    ScriptTargetSelectorArg,
    TargetKind,
    command_adapter,
)
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.lint import ScriptDeclarations
from repo2ree_protocol.queries import (
    BUILD_ARCHIVE,
    GET_HISTORY,
    GET_REE_DOCUMENT,
    GET_REE_DOCUMENT_SUMMARY,
    GET_REE_MANIFEST,
    GET_REVIEWS,
    INIT_REE,
    LINT_DRAFT,
    LINT_DRAFT_EXPERIMENT_ENVIRONMENT_PATH,
    LINT_DRAFT_EXPERIMENT_NAME,
    LIST_SCRIPT_TEMPLATES,
    READ_REE_FILE,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.verbs import REVIEW, SUMMARIES, VERBS, from_argv
from repo2ree_ree.layout import REE_MANIFEST
from repo2ree_ree.workbench_environment import EnvironmentBackend
from repo2ree_telemetry.log import configure_logging
from repo2ree_telemetry.relay import setup_relay_tracing

# The exit status of a run that was canceled, as a shell reports one stopped by SIGINT.
CANCELED = 130
# The exit status of a command refused for what was asked, as for a command line that spells none.
REFUSED = 2
_REFUSALS = ("validation", "precondition", "conflict")
# Where a staged archive comes from on the command line; the commands themselves name it by its upload token.
ARCHIVE_OPTION = "--archive"


@dataclass(frozen=True)
class Invocation:
    """What the options before the verb say: the REE, the output form, and the run's identity."""

    ree: Path | None
    machine: bool
    run_id: str | None
    context: ExecutionContext | None

    def layout(self) -> ReeLayout:
        return ReeLayout(root=self.ree or nearest_ree(Path.cwd()))

    def sink(self) -> LogSink:
        return _ndjson_sink if self.machine else _plain_sink


def nearest_ree(start: Path) -> Path:
    """The nearest directory at or above ``start`` that holds an REE; ``start`` itself when none does."""
    return next((path for path in (start, *start.parents) if (path / REE_MANIFEST).is_file()), start)


def _ndjson_sink(stream: str, level: str, message: str) -> None:
    click.echo(json.dumps({"type": "log", "stream": stream, "level": level, "message": message}), err=True)


def _plain_sink(stream: str, level: str, message: str) -> None:
    if stream == "system":
        click.echo(click.style(message, dim=level == "info", fg="red" if level == "error" else None), err=True)
    else:
        click.echo(message, err=True)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-C",
    "ree",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="The REE's directory; by default the nearest one at or above the current directory.",
)
@click.option(
    "--json",
    "machine",
    is_flag=True,
    help="Log events as NDJSON on stderr and the result as one JSON line on stdout.",
)
@click.option("--run-id", default=None, help="The run's id, which names its log in runs/.")
@click.option("--context", default=None, help="The run's invocation identity, as JSON.")
@click.pass_context
def cli(ctx: click.Context, ree: Path | None, machine: bool, run_id: str | None, context: str | None) -> None:
    """repo2ree: author, run, seal and review reproducible execution environments (REEs)."""
    ctx.obj = Invocation(
        ree=ree.resolve() if ree else None,
        machine=machine,
        run_id=run_id,
        context=ExecutionContext.model_validate_json(context) if context else None,
    )


def main() -> None:
    configure_logging()
    # Where the workbench gives the command line its pinned tools (git, curl, tar, …): first on PATH for it and the
    # processes it starts, while anything else keeps the PATH it had.
    if tools_bin := os.environ.get("REPO2REE_TOOLS_BIN"):
        os.environ["PATH"] = f"{tools_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    # The workbench asks for spans with TRACE_RELAY: they ride the NDJSON on stderr back to it.
    if os.environ.get("TRACE_RELAY"):
        setup_relay_tracing("repo2ree-cli", sys.stderr)
    cli()


# ================================================
# Commands
# ================================================


def _run(invocation: Invocation, verb: tuple[str, ...], command: type[BaseModel], words: list[str]) -> None:
    layout = invocation.layout()
    if command in (AcquireSourceCommand, LoadReeBundleCommand):
        words = _staged(layout, command, words)
    stdin = click.get_binary_stream("stdin").read() if reads_stdin(_args_of(command)) else None
    try:
        cmd = from_argv([*verb, *words], stdin)
    except (ArgvError, ValueError) as exc:
        raise click.UsageError(str(exc)) from exc
    result = run_session(
        cmd,
        layout=layout,
        runner=runner_from_environment(),
        emit=invocation.sink(),
        run_id=invocation.run_id,
        context=invocation.context,
        traceparent=os.environ.get("TRACEPARENT"),
    )
    _report(invocation, " ".join(verb), result)


def _report(invocation: Invocation, verb: str, result: ActionResult) -> None:
    if invocation.machine:
        # One bare ActionResult line on stdout: what the workbench reads.
        click.echo(result.model_dump_json())
    else:
        if result.outputs:
            click.echo(json.dumps(result.outputs, indent=2))
        why = f": {result.failure.message}" if result.failure else ""
        click.echo(f"{verb} {result.status}{why}", err=True)
    if result.status == "canceled":
        sys.exit(CANCELED)
    if result.status != "succeeded":
        sys.exit(REFUSED if result.failure and result.failure.category in _REFUSALS else 1)


def _staged(layout: ReeLayout, command: type[BaseModel], words: list[str]) -> list[str]:
    """``--archive PATH`` as the command takes it: the file staged in the REE, named by an upload token."""
    if ARCHIVE_OPTION not in words:
        return words
    at = words.index(ARCHIVE_OPTION)
    if at + 1 >= len(words):
        raise click.UsageError(f"{ARCHIVE_OPTION} needs a path")
    archive = Path(words[at + 1])
    if not archive.is_file():
        raise click.UsageError(f"no file {archive}")
    token = uuid4().hex
    staged = layout.upload_staging_file(token)
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(archive, staged)
    rest = [*words[:at], *words[at + 2 :], "--upload-token", token, "--archive-name", archive.name]
    if command is AcquireSourceCommand and "--mode" not in rest:
        rest += ["--mode", "upload"]
    return rest


def _args_of(command: type[BaseModel]) -> type[BaseModel]:
    return command.model_fields["args"].annotation  # type: ignore[return-value]


def _verb(verb: tuple[str, ...], command: type[BaseModel]) -> click.Command:
    args = _args_of(command)
    summary = SUMMARIES[command]
    usage = "\n".join(f"  {line}" for line in describe_args(args))
    if command in (AcquireSourceCommand, LoadReeBundleCommand):
        usage += f"\n  {ARCHIVE_OPTION} PATH, staged as the upload"

    @click.pass_obj
    def callback(invocation: Invocation, words: tuple[str, ...]) -> None:
        _run(invocation, verb, command, list(words))

    return click.Command(
        verb[-1],
        callback=callback,
        params=[click.Argument(["words"], nargs=-1, type=click.UNPROCESSED)],
        context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False},
        help=f"{summary}\n\n\b\nArguments:\n{usage}" if usage else summary,
        add_help_option=True,
    )


@cli.group(REVIEW)
def review() -> None:
    """Review a sealed REE: reproduce its steps in an attempt of their own and compare them with the author's."""


for _command, _words in VERBS.items():
    (review if _words[0] == REVIEW else cli).add_command(_verb(_words, _command))


@cli.command(INIT_REE)
@click.option("--name", required=True, help="The REE's name.")
@click.option(
    "--workbench-environment",
    type=click.Choice(get_args(EnvironmentBackend)),
    default="container",
    help="What the REE's scripts run in, which decides the scripts it starts with.",
)
@click.pass_obj
def init_cmd(invocation: Invocation, name: str, workbench_environment: EnvironmentBackend) -> None:
    """Create an REE here (or at -C) and capture its first version; again, it keeps what is there."""
    layout = ReeLayout(root=invocation.ree or Path.cwd())
    try:
        result = initialize_ree(layout, name=name, workbench_environment=workbench_environment)
    except HistoryCaptureError as exc:
        click.echo(json.dumps({"error": str(exc)}), err=True)
        raise click.exceptions.Exit(1) from exc
    click.echo(json.dumps({"status": result.status, "snapshot_id": result.snapshot_id}))


@cli.command("cancel")
@click.argument("run_id")
@click.pass_obj
def cancel_cmd(invocation: Invocation, run_id: str) -> None:
    """Ask the run RUN_ID to stop: it rolls the REE back and is captured as canceled."""
    request_cancel(invocation.layout(), run_id)
    click.echo(json.dumps({"status": "cancel_requested", "run_id": run_id}))


@cli.command("settle")
@click.argument("attempt_id")
@click.option("--command", "command_file", type=Path, default=None, help="The command it was started with, as JSON.")
@click.pass_obj
def settle_cmd(invocation: Invocation, attempt_id: str, command_file: Path | None) -> None:
    """Settle ATTEMPT_ID, whose process ended without reporting, and print how it ended.

    With its command, an attempt never recorded is recorded as having begun nothing. Prints nothing when the REE
    holds no such attempt and no command is given.
    """
    cmd = command_adapter.validate_json(command_file.read_text(encoding="utf-8")) if command_file else None
    result = settle_interrupted(
        layout=invocation.layout(),
        attempt_id=attempt_id,
        log=invocation.sink(),
        cmd=cmd,
        run_id=invocation.run_id,
        context=invocation.context,
    )
    if result is not None:
        click.echo(result.model_dump_json())


# ================================================
# Reading an REE
# ================================================


def _fail(message: str) -> NoReturn:
    click.echo(json.dumps({"error": message}), err=True)
    sys.exit(1)


@cli.command(GET_REE_MANIFEST)
@click.pass_obj
def manifest_cmd(invocation: Invocation) -> None:
    """Print the REE's record (ree.json)."""
    store = ReeDirectory(invocation.layout())
    if not store.manifest_exists():
        _fail("not initialised")
    click.echo(json.dumps(store.read_manifest_json()))


@cli.command(GET_REE_DOCUMENT)
@click.option(GET_REE_DOCUMENT_SUMMARY, "summary", is_flag=True, help="Leave out the files' contents.")
@click.pass_obj
def show_cmd(invocation: Invocation, summary: bool) -> None:
    """Print the REE as a document: its definition, evidence, audit and files."""
    try:
        result = get_ree_document(invocation.layout(), include_content=not summary)
    except FileNotFoundError as exc:
        _fail(str(exc))
    click.echo(result.model_dump_json())


@cli.command(GET_REVIEWS)
@click.pass_obj
def reviews_cmd(invocation: Invocation) -> None:
    """Print the REE's reviews, newest first."""
    click.echo(load_reviews(invocation.layout()).model_dump_json())


@cli.command(GET_HISTORY)
@click.pass_obj
def log_cmd(invocation: Invocation) -> None:
    """Print every attempt recorded in the REE's history and its reviews'."""
    click.echo(read_operation_history(invocation.layout()).model_dump_json())


@cli.command(BUILD_ARCHIVE)
@click.pass_obj
def bundle_cmd(invocation: Invocation) -> None:
    """Write the REE's portable bundle, with its histories, to stdout."""
    try:
        with materialized_ree_download(invocation.layout()) as path, path.open("rb") as archive:
            shutil.copyfileobj(archive, sys.stdout.buffer, length=1024 * 1024)
    except (FileNotFoundError, RuntimeError) as exc:
        _fail(str(exc))


@cli.command(READ_REE_FILE)
@click.argument("path")
@click.pass_obj
def cat_cmd(invocation: Invocation, path: str) -> None:
    """Write the bytes of PATH, a file anywhere in the REE, to stdout."""
    try:
        data = read_ree_file_bytes(invocation.layout(), path)
    except FileNotFoundError:
        _fail(f"not found: {path}")
    except ValueError as exc:
        _fail(str(exc))
    sys.stdout.buffer.write(data)


# ================================================
# Authoring
# ================================================


_MARKS = {"complete": "✓", "ready": "·", "blocked": "✗"}


@cli.command("steps")
@click.pass_obj
def steps_cmd(invocation: Invocation) -> None:
    """Show where the REE stands on each authoring step, and what to do next."""
    try:
        steps = get_ree_steps(invocation.layout())
    except FileNotFoundError as exc:
        _fail(str(exc))
    click.echo(steps.model_dump_json() if invocation.machine else _describe_steps(steps))


def _describe_steps(steps: ReeSteps) -> str:
    labels = {step.key: step.label for step in steps.steps}
    done = {step.key for step in steps.steps if step.status == "complete"}
    lines = []
    for step in steps.steps:
        mark = "→" if step.key == steps.next else _MARKS[step.status]
        line = f"{mark} {step.order:>2} {step.label}"
        if step.status == "blocked":
            line += f"  (needs {', '.join(labels[key] for key in step.requires if key not in done)})"
        lines.append(line)
    following = next((step for step in steps.steps if step.key == steps.next), None)
    if following is not None:
        lines += ["", f"next: {following.label}, with " + " or ".join(f"ree {words}" for words in following.commands)]
    elif len(done) == len(steps.steps):
        lines += ["", "every step is complete"]
    return "\n".join(lines)


@cli.command(LIST_SCRIPT_TEMPLATES)
def templates_cmd() -> None:
    """Print the starter templates for the REE's scripts and where each script belongs."""
    click.echo(script_template_catalog().model_dump_json())


@cli.command(LINT_DRAFT)
@click.argument("kind", type=click.Choice(get_args(TargetKind)))
@click.option(LINT_DRAFT_EXPERIMENT_NAME, "experiment_name", default=None, help="The experiment the script is for.")
@click.option(
    LINT_DRAFT_EXPERIMENT_ENVIRONMENT_PATH,
    "experiment_environment_path",
    default=None,
    help="The experiment environment's path the script is checked against.",
)
def lint_draft_cmd(kind: TargetKind, experiment_name: str | None, experiment_environment_path: str | None) -> None:
    """Check the unsaved script on stdin as the REE's KIND script, by the checks that run no process."""
    try:
        selector = ScriptTargetSelectorArg(kind=kind, experiment_name=experiment_name)
    except ValidationError as exc:
        raise click.UsageError(exc.errors()[0]["msg"]) from exc
    report = lint_script(
        resolve_target(selector),
        click.get_text_stream("stdin").read(),
        declarations=ScriptDeclarations(experiment_environment_path=experiment_environment_path),
        tiers=CONTRACT_ONLY,
    )
    click.echo(report.model_dump_json())


@cli.command("build-info")
def build_info_cmd() -> None:
    """Print this command line's build identity."""
    click.echo(current_build("repo2ree-cli").model_dump_json())


@cli.command("doctor")
@click.pass_obj
def doctor_cmd(invocation: Invocation) -> None:
    """Report what this machine offers an REE: a writable REE directory, the container engine, the tools.

    ``ok`` covers only what is required; the rest is for whoever runs the REE to judge.
    """
    click.echo(json.dumps(run_doctor(invocation.layout().root)))

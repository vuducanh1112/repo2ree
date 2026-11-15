from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, get_args

import click

from repo2ree_core.bundle.download import materialized_ree_download
from repo2ree_core.doctor import run_doctor
from repo2ree_core.evidence.review.store import load_reviews
from repo2ree_core.execution.runners import runner_from_environment
from repo2ree_core.operations.capture import settle_interrupted
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.read_models.files import read_ree_file_bytes as _read_ree_file_bytes
from repo2ree_core.operations.read_models.ree_document import get_ree_document as _get_ree_document
from repo2ree_core.operations.session import request_cancel, run_session
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.reproduction.commands import (
    BUILD_EXPERIMENT_ENVIRONMENT,
    EXPERIMENT,
    MATERIALIZE_WORKSPACE,
    TEST_ACTIVATION,
)
from repo2ree_protocol.build import current_build
from repo2ree_protocol.command import (
    ActivationTestArgs,
    ActivationTestCommand,
    BuildExperimentEnvironmentCommand,
    MaterializeWorkspaceCommand,
    RunExperimentArgs,
    RunExperimentCommand,
    command_adapter,
)
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.queries import (
    BUILD_ARCHIVE,
    GET_HISTORY,
    GET_REE_DOCUMENT,
    GET_REE_DOCUMENT_SUMMARY,
    GET_REE_MANIFEST,
    GET_REVIEWS,
    READ_REE_FILE,
    READ_REE_FILE_PATH,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.workbench_environment import EnvironmentBackend
from repo2ree_telemetry.log import configure_logging as _configure_logging
from repo2ree_telemetry.relay import setup_relay_tracing

# ================================================
# Logging
# ================================================


def _stderr_sink(stream: str, level: str, message: str) -> None:
    """One log event as an NDJSON line on stderr: the wire protocol the workbench parses."""
    click.echo(json.dumps({"type": "log", "stream": stream, "level": level, "message": message}), file=sys.stderr)


# ================================================
# Root CLI group
# ================================================


@click.group()
def cli() -> None:
    """repo2ree — build and run reproducible execution environments."""


def main() -> None:
    # Plain (unstructured) root logs: the executor's meaningful logs ride the
    # LogSink NDJSON relay, and it has no path to a collector anyway.
    _configure_logging()
    # On injected benches the workbench advertises a symlink farm of handler/
    # lifecycle tools (git, curl, tar, …). Prepending it here — rather than to
    # the container env — scopes it to the executor and its subprocesses: user
    # scripts get pinned nix tools (deterministic over whatever the image
    # ships), while processes outside the executor keep the image's own PATH.
    tools_bin = os.environ.get("REPO2REE_TOOLS_BIN")
    if tools_bin:
        os.environ["PATH"] = f"{tools_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    # The supervisor sets TRACE_RELAY when it wants spans; they ride the stderr
    # NDJSON stream back to it (this process has no path to the collector).
    if os.environ.get("TRACE_RELAY"):
        setup_relay_tracing("repo2ree-cli", sys.stderr)
    cli()


# ================================================
# Execution commands
# ================================================


@cli.command("execute")
@click.option(
    "--action",
    "action_source",
    default="-",
    show_default=True,
    help="Path to action JSON file, or '-' to read from stdin.",
)
@click.option(
    "--run-id",
    default=None,
    help="If set, append NDJSON events to /ree/runs/<run-id>.ndjson.",
)
@click.option("--execution-context", default=None, help="Serialized invocation identity.")
def execute_cmd(action_source: str, run_id: str | None, execution_context: str | None) -> None:
    """Execute a typed Command envelope (JSON).

    The dispatcher calls this with the serialised Command on stdin:

        docker exec <workbench> repo2ree execute --action -

    Emits NDJSON log events to stderr during execution.
    Writes a single ActionResult JSON line to stdout on completion.
    Exits non-zero on failure or cancellation.
    """
    if action_source == "-":
        text = click.get_text_stream("stdin").read()
    else:
        text = Path(action_source).read_text(encoding="utf-8")

    try:
        cmd = command_adapter.validate_json(text)
        context = (
            ExecutionContext.model_validate_json(execution_context) if execution_context else ExecutionContext.new()
        )
    except Exception as exc:  # noqa: BLE001 — malformed input is reported on the wire as a log frame, not as a traceback
        click.echo(
            json.dumps(
                {
                    "type": "log",
                    "stream": "system",
                    "level": "error",
                    "message": f"invalid action JSON — {exc}",
                }
            ),
            file=sys.stderr,
        )
        sys.exit(2)

    _run_command_envelope(cmd, run_id, context)


def _run_command_envelope(cmd: Any, run_id: str | None, context: ExecutionContext | None = None) -> None:
    """Run a validated Command in this REE: NDJSON log frames on stderr, one ActionResult line on stdout.

    Exits non-zero on failure or cancellation.
    """
    result = run_session(
        cmd,
        layout=ReeLayout.in_workbench(),
        runner=runner_from_environment(),
        emit=_stderr_sink,
        run_id=run_id,
        context=context,
        traceparent=os.environ.get("TRACEPARENT"),
    )
    # stdout stays the wire protocol, byte for byte: one bare ActionResult line is what the dispatcher parses.
    click.echo(result.model_dump_json())
    if result.status != "succeeded":
        sys.exit(1)


@cli.command("cancel-run")
@click.option("--run-id", required=True, help="The action run id to cancel.")
def cancel_run_cmd(run_id: str) -> None:
    """Mark a running command envelope as canceled inside the workbench."""
    request_cancel(ReeLayout.in_workbench(), run_id)
    click.echo(json.dumps({"status": "cancel_requested", "run_id": run_id}))


@cli.command("settle-attempt")
@click.option("--attempt-id", required=True, help="The attempt whose executor ended without reporting.")
@click.option("--action", "action_source", default=None, help="The command it was started with, as a file.")
@click.option("--run-id", default=None, help="The run it was started for.")
@click.option("--execution-context", default=None, help="The serialized invocation identity it was started with.")
def settle_attempt_cmd(
    attempt_id: str, action_source: str | None, run_id: str | None, execution_context: str | None
) -> None:
    """Settle the attempt of an executor that ended without reporting, and write how it ended.

    With the command, an attempt the executor never recorded is recorded as having begun nothing.
    Writes nothing when the REE holds no such attempt and no command is given.
    """
    cmd = command_adapter.validate_json(Path(action_source).read_text(encoding="utf-8")) if action_source else None
    context = ExecutionContext.model_validate_json(execution_context) if execution_context else None
    result = settle_interrupted(
        layout=ReeLayout.in_workbench(),
        attempt_id=attempt_id,
        log=_stderr_sink,
        cmd=cmd,
        run_id=run_id,
        context=context,
    )
    if result is not None:
        click.echo(result.model_dump_json())


# ================================================
# Reproduction commands
# ================================================
#
# First-class verbs that mirror the bundle's run.sh (see
# repo2ree_core.reproduction). Each is sugar over an `execute` envelope so the
# human/CI surface and the machine surface (host → workbench) share one path.
# Acquiring a source is deliberately *not* here: it is the one verb that
# changes what the REE is, so in a workbench it has to go through the acquire
# lifecycle (which decides whether it is legal and commits what it produced).
# Run bare, it would leave source on disk the REE never recorded — exactly the
# state that lifecycle refuses on. The bundle's `run.sh acquire-source` is a
# different surface: self-contained shell, no REE to keep consistent.


@cli.command(MATERIALIZE_WORKSPACE.name, help=MATERIALIZE_WORKSPACE.summary)
@click.option("--run-id", default=None, help="If set, append NDJSON events to /ree/runs/<run-id>.ndjson.")
def materialize_workspace_cmd(run_id: str | None) -> None:
    _run_command_envelope(MaterializeWorkspaceCommand(), run_id)


@cli.command(BUILD_EXPERIMENT_ENVIRONMENT.name, help=BUILD_EXPERIMENT_ENVIRONMENT.summary)
@click.option("--run-id", default=None, help="If set, append NDJSON events to /ree/runs/<run-id>.ndjson.")
def build_experiment_environment_cmd(run_id: str | None) -> None:
    _run_command_envelope(BuildExperimentEnvironmentCommand(), run_id)


@cli.command(TEST_ACTIVATION.name, help=TEST_ACTIVATION.summary)
@click.option("--run-id", default=None, help="If set, append NDJSON events to /ree/runs/<run-id>.ndjson.")
def test_activation_cmd(run_id: str | None) -> None:
    _run_command_envelope(ActivationTestCommand(args=ActivationTestArgs()), run_id)


@cli.command(EXPERIMENT.name, help=EXPERIMENT.summary)
@click.argument("name")
@click.option("--run-id", default=None, help="If set, append NDJSON events to /ree/runs/<run-id>.ndjson.")
def experiment_cmd(name: str, run_id: str | None) -> None:
    _run_command_envelope(
        RunExperimentCommand(args=RunExperimentArgs(experiment_name=name)),
        run_id,
    )


@cli.command("init-ree")
@click.option("--name", required=True, help="Human-readable name for the REE.")
@click.option(
    "--workbench-environment",
    type=click.Choice(get_args(EnvironmentBackend)),
    default="container",
    help="What the REE's scripts run in, which decides the scripts it starts with.",
)
def init_ree_cmd(name: str, workbench_environment: EnvironmentBackend) -> None:
    """Initialize the REE through core and capture its first Git version.

    Retrying preserves existing files and ensures a baseline exists. A capture
    failure can leave initialized files; a later invocation retries the capture.
    """
    try:
        result = initialize_ree(ReeLayout.in_workbench(), name=name, workbench_environment=workbench_environment)
    except HistoryCaptureError as exc:
        click.echo(json.dumps({"error": str(exc)}), err=True)
        raise click.exceptions.Exit(1) from exc
    click.echo(json.dumps({"status": result.status, "snapshot_id": result.snapshot_id}))


# ================================================
# Inspection commands
# ================================================


@cli.command("build-info")
def build_info_cmd() -> None:
    """Print this executor's build identity as JSON."""
    click.echo(current_build("repo2ree-cli").model_dump_json())


@cli.command("doctor")
def doctor_cmd() -> None:
    """Probe this bench's capabilities and emit the report as JSON.

    The workbench runs this right after provisioning a bench: ``ok`` covers the
    hard bench contract (writable /ree), the rest is capability inventory
    (docker substrate, handler tools). Exits non-zero only when the probe
    itself cannot run — a not-ok report is the workbench's call to make.
    """
    click.echo(json.dumps(run_doctor()))


@cli.command(GET_REE_MANIFEST)
def get_ree_manifest_cmd() -> None:
    """Emit the persisted REE record as JSON.

    Reads ree.json from /ree. Exits non-zero if not initialised.
    """
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)

    if not store.manifest_exists():
        click.echo(json.dumps({"error": "not initialised"}), file=sys.stderr)
        sys.exit(1)

    click.echo(json.dumps(store.read_manifest_json()))


@cli.command(GET_REE_DOCUMENT)
@click.option(GET_REE_DOCUMENT_SUMMARY, "summary", is_flag=True, help="Omit inline file content from the REE document.")
def get_ree_document_cmd(summary: bool) -> None:
    """Emit the composed REE document as JSON.

    Equivalent to the core get_ree_document() read model but executed inside the
    workbench container so the output reflects the workbench volume.
    """
    # The document carries no REE id: the control plane stamps it on the way back.
    try:
        result = _get_ree_document(ReeLayout.in_workbench(), include_content=not summary)
    except FileNotFoundError as exc:
        click.echo(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    click.echo(result.model_dump_json())


@cli.command(GET_REVIEWS)
def get_reviews_cmd() -> None:
    """Emit persisted review attempts, newest first."""
    click.echo(load_reviews(ReeLayout.in_workbench()).model_dump_json())


@cli.command(GET_HISTORY)
def get_history_cmd() -> None:
    """Read operation records from author and review histories."""
    click.echo(read_operation_history(ReeLayout.in_workbench()).model_dump_json())


@cli.command(BUILD_ARCHIVE)
def build_archive_cmd() -> None:
    """Write a portable REE bundle and Git histories in one download."""
    try:
        with (
            materialized_ree_download(ReeLayout.in_workbench()) as archive_path,
            archive_path.open("rb") as archive,
        ):
            shutil.copyfileobj(archive, sys.stdout.buffer, length=1024 * 1024)
    except (FileNotFoundError, RuntimeError) as exc:
        click.echo(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)


@cli.command(READ_REE_FILE)
@click.option(READ_REE_FILE_PATH, "file_path", required=True, help="Path relative to the REE root")
def read_ree_file_cmd(file_path: str) -> None:
    """Write raw bytes of any regular file inside the REE."""
    try:
        data = _read_ree_file_bytes(ReeLayout.in_workbench(), file_path)
    except FileNotFoundError:
        click.echo(json.dumps({"error": f"not found: {file_path}"}), file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        click.echo(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    sys.stdout.buffer.write(data)


# ================================================
# Helpers
# ================================================


def _emit_result(result: ActionResult) -> None:
    click.echo(result.model_dump_json())
    if result.status != "succeeded":
        sys.exit(1)

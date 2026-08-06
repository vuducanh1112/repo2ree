from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, TextIO

import click

from repo2ree_core.bundle.seal import build_ree_archive as _build_archive
from repo2ree_core.digests import digest_file
from repo2ree_core.doctor import run_doctor
from repo2ree_core.domain.ree.model import (
    BuildRuntimeDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
    TestActivationDefinition,
)
from repo2ree_core.evidence.review.store import load_reviews
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.read_models.files import read_ree_file_bytes as _read_ree_file_bytes
from repo2ree_core.operations.read_models.ree_document import get_ree_document as _get_ree_document
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.reproduction.commands import (
    BUILD_RUNTIME,
    EXPERIMENT,
    MATERIALIZE_WORKSPACE,
    TEST_ACTIVATION,
)
from repo2ree_core.reserved_paths import RESERVED_ACTIVATION_SCRIPT, RESERVED_BUILD_SCRIPT
from repo2ree_protocol import ActionResult, command_adapter
from repo2ree_protocol.command import (
    ActivationTestArgs,
    ActivationTestCommand,
    BuildRuntimeCommand,
    MaterializeWorkspaceCommand,
    RunExperimentArgs,
    RunExperimentCommand,
)
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.log import configure_logging as _configure_logging
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    attach_remote_context,
    detach_context,
    get_tracer,
    record_command_status,
    record_exit_code,
    setup_relay_tracing,
)

tracer = get_tracer(__name__)

# ================================================
# Logging
# ================================================


def _write_run_log_frame(run_log: TextIO | None, run_id: str | None, frame: dict[str, Any]) -> None:
    """Append one self-describing NDJSON frame to the run log.

    Every frame names its own ``type`` and the run it belongs to, so a reader
    can filter lines without tracking position and without reading the file
    name — ``jq 'select(.type == "command")'`` over any concatenation of run
    logs is the whole parse. ``run_id`` is what joins a frame to the span that
    covered the same work and to the receipt it produced; the ``Command`` itself
    does not carry one, so it has to be stamped here.
    """
    if run_log is None:
        return
    run_log.write(json.dumps({"run_id": run_id, **frame}) + "\n")
    run_log.flush()


def _make_log_sink(run_log: TextIO | None, run_id: str | None = None) -> LogSink:
    """Return a LogSink that emits NDJSON to stderr (and optionally a run log file).

    The two destinations carry the same event in deliberately different shapes.
    stderr is the wire protocol the supervisor parses, so it stays exactly as it
    has been. The file copy is stamped with ``run_id`` like every other frame,
    because a run log is read on its own — often concatenated with others — and
    a line that cannot say which run it belongs to is not much of a record.
    """

    def _log(stream: str, level: str, message: str) -> None:
        event = {"type": "log", "stream": stream, "level": level, "message": message}
        click.echo(json.dumps(event), file=sys.stderr)
        _write_run_log_frame(run_log, run_id, event)

    return _log


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
    # On injected benches the agent advertises a symlink farm of handler/
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
        setup_relay_tracing("repo2ree-exec", sys.stderr)
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
def execute_cmd(action_source: str, run_id: str | None) -> None:
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

    _run_command_envelope(cmd, run_id)


def _run_command_envelope(cmd: Any, run_id: str | None) -> None:
    """Run a validated Command envelope, streaming NDJSON and emitting the result.

    Shared by ``execute`` (the machine path, host → workbench) and the
    first-class reproduction subcommands (``build-runtime``, ``test-activation``,
    ``experiment``, ``materialize-workspace``) so they all log, persist, and
    signal failure identically. Exits non-zero on failure or cancellation.
    """
    run_log: TextIO | None = None
    cancel_marker: Path | None = None
    if run_id is not None:
        layout = ReeLayout.in_workbench()
        # Review commands stream their logs into their own attempt namespace so
        # reviewer evidence never lands in the author's runs/. Recognised by the
        # arg they all carry, so a new review step needs no branch here.
        review_id = getattr(cmd.args, "review_id", None)
        evidence_layout: ReeLayout | ReviewLayout = layout.review(review_id) if review_id else layout
        evidence_layout.runs.mkdir(parents=True, exist_ok=True)
        run_log = evidence_layout.run_log(run_id).open("a", encoding="utf-8")
        cancel_marker = layout.run_cancel_marker(run_id)
    is_canceled = (lambda marker=cancel_marker: marker.exists()) if cancel_marker is not None else None

    # The command as it arrived, whole and untruncated. Its counterpart on the
    # way out is the result frame below, and the two together are the complete
    # contract of one operation — the same pair the command span carries as
    # `repo2ree.arg.*` / `repo2ree.output.*`, but there summarized to fit a
    # span (strings elided, payloads reduced to a size) and here kept entire.
    # Joined to that span, and to the receipt the operation files, by run_id.
    _write_run_log_frame(
        run_log,
        run_id,
        {"type": "command", "operation": str(cmd.operation), "command": cmd.model_dump(mode="json")},
    )

    # Attach the dispatcher's trace context (forwarded via TRACEPARENT) so this
    # process's spans hang under the host-side dispatch span.
    ctx_token = attach_remote_context(os.environ.get("TRACEPARENT"))
    try:
        log = _make_log_sink(run_log, run_id)
        # The executor process itself, as one span. Without it a trace steps
        # straight from the supervisor's `docker exec` into core's command span
        # and the process boundary is nowhere in the picture — which also means
        # the interpreter start-up before this line is charged to the dispatch
        # that was waiting on it, with nothing to attribute it to. Opened here
        # rather than at the CLI entry point because this is the first moment a
        # command exists to name.
        with tracer.start_as_current_span(f"executor.{cmd.operation}") as span:
            CommandSpanAttrs(operation=str(cmd.operation), run_id=run_id).apply(span)
            result = run_command(
                cmd,
                log=log,
                run_id=run_id,
                is_canceled=is_canceled,
            )
            record_exit_code(span, result.exit_code)
            record_command_status(span, result.status)
        # stdout stays the wire protocol, byte for byte: one bare ActionResult
        # line is what the dispatcher parses. The run log gets the same value
        # wrapped in a named frame, which only the file needs.
        click.echo(result.model_dump_json())
        _write_run_log_frame(
            run_log,
            run_id,
            {"type": "result", "operation": str(cmd.operation), "result": result.model_dump(mode="json")},
        )
    finally:
        detach_context(ctx_token)
        if run_log is not None:
            run_log.close()
        # Each run clears its own marker so cancellation correctness never
        # depends on run ids being globally unique: a stale marker left behind
        # would otherwise cancel a later run that happened to reuse the id.
        if cancel_marker is not None:
            cancel_marker.unlink(missing_ok=True)

    if result.status != "succeeded":
        sys.exit(1)


@cli.command("cancel-run")
@click.option("--run-id", required=True, help="The action run id to cancel.")
def cancel_run_cmd(run_id: str) -> None:
    """Mark a running command envelope as canceled inside the workbench."""
    layout = ReeLayout.in_workbench()
    layout.runs.mkdir(parents=True, exist_ok=True)
    layout.run_cancel_marker(run_id).touch()
    click.echo(json.dumps({"status": "cancel_requested", "run_id": run_id}))


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


@cli.command(BUILD_RUNTIME.name, help=BUILD_RUNTIME.summary)
@click.option("--run-id", default=None, help="If set, append NDJSON events to /ree/runs/<run-id>.ndjson.")
def build_runtime_cmd(run_id: str | None) -> None:
    _run_command_envelope(BuildRuntimeCommand(), run_id)


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
def init_ree_cmd(name: str) -> None:
    """Initialise the REE directory structure at /ree.

    Creates the directory skeleton and writes an initial ree.json.
    Idempotent: exits 0 without modifying anything if already initialised.

    Takes no identifier: an REE is addressed by the tree it lives in, which is
    always ``/ree`` here. The handle its control plane files it under is that
    control plane's own (see ``WorkbenchManager._with_handle``) and nothing in
    the workbench could confirm or contradict it.
    """
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)

    if store.manifest_exists():
        click.echo(json.dumps({"status": "already_initialised"}))
        return

    store.ensure_dirs()
    store.ensure_reserved_overlay_scripts()

    build_path = store.overlay.absolute(RESERVED_BUILD_SCRIPT)
    activation_path = store.overlay.absolute(RESERVED_ACTIVATION_SCRIPT)
    store.write_ree(
        Ree(
            subject=ReeSubject(
                definition=ReeDefinition(
                    name=name,
                    build_runtime=BuildRuntimeDefinition(
                        build_runtime_script_digest=digest_file(build_path),
                        build_runtime_script_size=build_path.stat().st_size,
                    ),
                    test_activation=TestActivationDefinition(
                        run_script_digest=digest_file(activation_path),
                        run_script_size=activation_path.stat().st_size,
                    ),
                ),
            )
        )
    )
    click.echo(json.dumps({"status": "initialised"}))


# ================================================
# Inspection commands
# ================================================


@cli.command("doctor")
def doctor_cmd() -> None:
    """Probe this bench's capabilities and emit the report as JSON.

    The agent runs this right after provisioning a bench: ``ok`` covers the
    hard bench contract (writable /ree), the rest is capability inventory
    (docker substrate, handler tools). Exits non-zero only when the probe
    itself cannot run — a not-ok report is the agent's call to make.
    """
    click.echo(json.dumps(run_doctor()))


@cli.command("get-ree-manifest")
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


@cli.command("get-ree-document")
@click.option("--summary", is_flag=True, help="Omit inline file content from the REE document.")
def get_ree_document_cmd(summary: bool) -> None:
    """Emit the composed REE document as JSON.

    Equivalent to the core get_ree_document() read model but executed inside the
    workbench container so the output reflects the workbench volume.
    """
    # The document carries no handle: the control plane stamps the real one on
    # the way back (see WorkbenchManager._with_handle).
    try:
        result = _get_ree_document(ReeLayout.in_workbench(), include_content=not summary)
    except FileNotFoundError as exc:
        click.echo(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    click.echo(result.model_dump_json())


@cli.command("get-reviews")
def get_reviews_cmd() -> None:
    """Emit persisted review attempts, newest first."""
    click.echo(load_reviews(ReeLayout.in_workbench()).model_dump_json())


@cli.command("build-archive")
def build_archive_cmd() -> None:
    """Write the sealed REE zip archive bytes to stdout."""
    try:
        data = _build_archive(ReeLayout.in_workbench())
    except (FileNotFoundError, RuntimeError) as exc:
        click.echo(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    sys.stdout.buffer.write(data)


@cli.command("read-ree-file")
@click.option("--path", "file_path", required=True, help="Path relative to the REE root")
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

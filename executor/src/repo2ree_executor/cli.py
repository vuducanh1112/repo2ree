from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, TextIO

import click

from repo2ree_core.bundle.seal import build_ree_archive as _build_archive
from repo2ree_core.doctor import run_doctor
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.evidence.review.store import load_reviews
from repo2ree_core.evidence.scorecard import build_scorecard
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.read_models.files import read_ree_file_bytes as _read_ree_file_bytes
from repo2ree_core.operations.read_models.ree_document import get_ree_document as _get_ree_document
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.persistence.receipts import load_author_receipts
from repo2ree_core.persistence.record import ReeRecord
from repo2ree_core.reproduction import (
    BUILD_RUNTIME,
    EXPERIMENT,
    MATERIALIZE_WORKSPACE,
    TEST_ACTIVATION,
)
from repo2ree_core.time_utils import utc_now as _utc_now
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
    attach_remote_context,
    detach_context,
    setup_relay_tracing,
)

# ================================================
# Logging
# ================================================


def _make_log_sink(run_log: TextIO | None) -> LogSink:
    """Return a LogSink that emits NDJSON to stderr (and optionally a run log file)."""

    def _log(stream: str, level: str, message: str) -> None:
        event = json.dumps({"type": "log", "stream": stream, "level": level, "message": message})
        click.echo(event, file=sys.stderr)
        if run_log is not None:
            run_log.write(event + "\n")
            run_log.flush()

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

    # Attach the dispatcher's trace context (forwarded via TRACEPARENT) so the
    # command span hangs under the host-side dispatch span.
    ctx_token = attach_remote_context(os.environ.get("TRACEPARENT"))
    try:
        log = _make_log_sink(run_log)
        result = run_command(
            cmd,
            log=log,
            run_id=run_id or "manual",
            is_canceled=is_canceled,
        )
        result_line = result.model_dump_json()
        click.echo(result_line)
        if run_log is not None:
            run_log.write(json.dumps({"type": "result"}) + "\n")
            run_log.write(result_line + "\n")
            run_log.flush()
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
@click.option("--ree-id", required=True, help="The REE identifier.")
@click.option("--name", default=None, help="Human-readable name for the REE.")
def init_ree_cmd(ree_id: str, name: str | None) -> None:
    """Initialise the REE directory structure at /ree.

    Creates the directory skeleton and writes an initial .ree.json.
    Idempotent: exits 0 without modifying anything if already initialised.
    """
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)

    if store.record_exists():
        click.echo(json.dumps({"status": "already_initialised", "ree_id": ree_id}))
        return

    store.ensure_dirs()
    store.ensure_reserved_overlay_scripts()

    ts = _utc_now()
    ree_name = name or f"ree-{ree_id[:8]}"
    store.write_record(
        ReeRecord(
            ree_id=ree_id,
            name=ree_name,
            status="draft",
            created_at=ts,
            updated_at=ts,
            ree_intent=ReeIntent(name=ree_name),
            ree_state=ReeLifecycleState(),
        )
    )
    click.echo(json.dumps({"status": "initialised", "ree_id": ree_id}))


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


@cli.command("get-ree-record")
def get_ree_record_cmd() -> None:
    """Emit the persisted REE record as JSON.

    Reads .ree.json from /ree. Exits non-zero if not initialised.
    """
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)

    if not store.record_exists():
        click.echo(json.dumps({"error": "not initialised"}), file=sys.stderr)
        sys.exit(1)

    record = store.read_record_json()
    click.echo(json.dumps(record))


@cli.command("get-ree-document")
@click.option("--summary", is_flag=True, help="Omit inline file content from the REE document.")
def get_ree_document_cmd(summary: bool) -> None:
    """Emit the composed REE document as JSON.

    Equivalent to the core get_ree_document() read model but executed inside the
    workbench container so the output reflects the workbench volume.
    """
    layout = ReeLayout.in_workbench()
    # The core read views use (storage_root, ree_id) addressing; the workbench
    # volume is mounted at /ree, which maps to storage_root=/ and ree_id=ree.
    storage_root = layout.root.parent
    ree_id = layout.root.name
    try:
        result = _get_ree_document(storage_root, ree_id, include_content=not summary)
    except FileNotFoundError as exc:
        click.echo(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    click.echo(result.model_dump_json())


@cli.command("get-scorecard")
def get_scorecard_cmd() -> None:
    """Emit the reproducibility scorecard as JSON.

    Computed purely from the persisted record (intent + state + run
    receipts), so the same scorecard is recomputable from a sealed bundle.
    Exits non-zero if not initialised.
    """
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)

    if not store.record_exists():
        click.echo(json.dumps({"error": "not initialised"}), file=sys.stderr)
        sys.exit(1)

    record = store.read_record()
    card = build_scorecard(
        record.ree_intent,
        record.ree_state,
        list(load_author_receipts(layout).values()),
    )
    click.echo(card.model_dump_json())


@cli.command("get-reviews")
def get_reviews_cmd() -> None:
    """Emit persisted review attempts, newest first."""
    click.echo(load_reviews(ReeLayout.in_workbench()).model_dump_json())


@cli.command("build-archive")
def build_archive_cmd() -> None:
    """Write the sealed REE zip archive bytes to stdout."""
    layout = ReeLayout.in_workbench()
    storage_root = layout.root.parent
    ree_id = layout.root.name
    try:
        data = _build_archive(storage_root, ree_id)
    except (FileNotFoundError, RuntimeError) as exc:
        click.echo(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    sys.stdout.buffer.write(data)


@cli.command("read-ree-file")
@click.option("--path", "file_path", required=True, help="Path relative to the REE root")
def read_ree_file_cmd(file_path: str) -> None:
    """Write raw bytes of any regular file inside the REE."""
    layout = ReeLayout.in_workbench()
    storage_root = layout.root.parent
    ree_id = layout.root.name
    try:
        data = _read_ree_file_bytes(storage_root, ree_id, file_path)
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

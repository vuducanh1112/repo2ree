from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

import click

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.envelope.run_command import run_command
from repo2ree_core.storage.receipt_journal import ReceiptJournal
from repo2ree_executor.journal import (
    elide_large_outputs,
    prepare_command,
    snapshot_ree_digest,
)
from repo2ree_protocol import ActionResult, command_adapter
from repo2ree_protocol.command import AcquireSourceArgs, AcquireSourceCommand
from repo2ree_protocol.receipt import (
    NON_JOURNALED_OPERATIONS,
    ReceiptClose,
    ReceiptOpen,
)
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.storage.workspace_ops import (
    build_workspace_ree_archive as _build_archive,
)
from repo2ree_core.storage.workspace_ops import get_workspace as _get_workspace
from repo2ree_core.storage.workspace_ops import read_file_bytes as _read_file_bytes


# ================================================
# Logging
# ================================================


def _make_log_sink(run_log: TextIO | None):
    """Return a LogSink that emits NDJSON to stderr (and optionally a run log file)."""

    def _log(stream: str, level: str, message: str) -> None:
        event = json.dumps(
            {"type": "log", "stream": stream, "level": level, "message": message}
        )
        click.echo(event, file=sys.stderr)
        if run_log is not None:
            run_log.write(event + "\n")
            run_log.flush()

    return _log


# ================================================
# Helpers
# ================================================


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ================================================
# Root CLI group
# ================================================


@click.group()
def cli() -> None:
    """repo2ree — build and run reproducible execution environments."""


def main() -> None:
    cli()


# ================================================
# execute (generic Command envelope)
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
    except Exception as exc:
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

    layout = ReeLayout.in_workbench()
    run_log: TextIO | None = None
    if run_id is not None:
        layout.runs.mkdir(parents=True, exist_ok=True)
        run_log = layout.run_log(run_id).open("a", encoding="utf-8")

    try:
        log = _make_log_sink(run_log)
        started_at = _utc_now()

        # Two-phase journal protocol for structural operations:
        #
        # Phase 0 (dangling-open recovery):
        #   Before writing a new open, check whether the previous executor process
        #   left a dangling open (crashed after open but before close).  If so,
        #   compare input_digest against the current REE state to determine whether
        #   the action's side effects were applied, then write a recovery close so
        #   the journal is self-consistent before the new action starts.
        #
        # Phase 1 (open — write-ahead, before execution):
        #   Write ReceiptOpen with the input_digest of the REE state.  If this
        #   write fails we abort *before* touching the REE — the caller sees
        #   "failed" and the REE state is unchanged, so retry is safe.
        #
        # Phase 2 (close — finalization, after execution):
        #   Write ReceiptClose with the outcome.  If the close write fails, attempt
        #   an abort-close (same receipt_id, status="failed") so the open does not
        #   remain dangling.  If even the abort-close fails, the open is dangling —
        #   the action's side effects stand but its outcome is unrecorded.  Returning
        #   "failed" here causes the host to retry; since all current structural ops
        #   are idempotent, the retry produces a fresh open+close pair, and the
        #   original dangling open remains as a visible checkpoint artifact.
        journal: ReceiptJournal | None = None
        receipt_id: str | None = None
        open_written = False

        if cmd.operation not in NON_JOURNALED_OPERATIONS:
            journal = ReceiptJournal(layout)

            # Phase 0: recover any dangling open from a previous crash.
            dangling = journal.dangling_open()
            if dangling is not None:
                current_digest = snapshot_ree_digest(layout)
                if dangling.input_digest == current_digest:
                    recovery_note = "no_effect_detected"
                else:
                    recovery_note = "state_changed"
                log(
                    "system",
                    "warning",
                    f"dangling open {dangling.receipt_id!r} ({dangling.operation}) — "
                    f"writing recovery close ({recovery_note})",
                )
                try:
                    journal.append_close(
                        ReceiptClose(
                            receipt_id=dangling.receipt_id,
                            status="failed",
                            exit_code=1,
                            outputs={"recovery": recovery_note},
                            finished_at=_utc_now(),
                            output_digest=current_digest,
                        )
                    )
                except Exception as exc:
                    log(
                        "system",
                        "error",
                        f"recovery close write failed: {exc}; dangling open persists",
                    )

            command_dict = json.loads(cmd.model_dump_json())
            action_digest, stored_command = prepare_command(command_dict)
            receipt_id = uuid.uuid4().hex
            try:
                journal.append_open(
                    ReceiptOpen(
                        receipt_id=receipt_id,
                        operation=cmd.operation,
                        command=stored_command,
                        action_digest=action_digest,
                        input_digest=snapshot_ree_digest(layout),
                        started_at=started_at,
                        predecessor=journal.last_receipt_id(),
                        log_ref=run_id,
                    )
                )
                open_written = True
            except Exception as exc:
                log(
                    "system",
                    "error",
                    f"open-receipt write failed; aborting before execution: {exc}",
                )
                result = ActionResult(
                    status="failed",
                    exit_code=1,
                    outputs={"checkpoint_error": f"journal open failed: {exc}"},
                )
                result_line = result.model_dump_json()
                click.echo(result_line)
                if run_log is not None:
                    run_log.write(json.dumps({"type": "result"}) + "\n")
                    run_log.write(result_line + "\n")
                    run_log.flush()
                sys.exit(1)

        try:
            result = run_command(cmd, log=log, run_id=run_id or "manual")
        except Exception as exc:
            log("system", "error", f"{cmd.operation} raised: {exc}")
            result = ActionResult(
                status="failed", exit_code=1, outputs={"error": str(exc)}
            )
        finished_at = _utc_now()

        if journal is not None and open_written and receipt_id is not None:
            close = ReceiptClose(
                receipt_id=receipt_id,
                status=result.status,
                exit_code=result.exit_code,
                outputs=elide_large_outputs(result.outputs),
                finished_at=finished_at,
                output_digest=snapshot_ree_digest(layout),
            )
            try:
                journal.append_close(close)
            except Exception as exc:
                log(
                    "system",
                    "error",
                    f"close-receipt write failed after execution: {exc}; attempting abort-close",
                )
                try:
                    journal.append_close(
                        ReceiptClose(
                            receipt_id=receipt_id,
                            status="failed",
                            exit_code=1,
                            outputs={"checkpoint_error": f"close write failed: {exc}"},
                            finished_at=_utc_now(),
                        )
                    )
                except Exception as exc2:
                    log(
                        "system",
                        "error",
                        f"abort-close also failed: {exc2}; journal has dangling open",
                    )
                result = ActionResult(
                    status="failed",
                    exit_code=1,
                    outputs={
                        **result.outputs,
                        "checkpoint_error": f"close write failed: {exc}",
                    },
                )

        result_line = result.model_dump_json()
        click.echo(result_line)
        if run_log is not None:
            run_log.write(json.dumps({"type": "result"}) + "\n")
            run_log.write(result_line + "\n")
            run_log.flush()
    finally:
        if run_log is not None:
            run_log.close()

    if result.status != "succeeded":
        sys.exit(1)


# ================================================
# acquire-source  (argv-sugar path)
# ================================================


@cli.command("acquire-source")
@click.argument("origin_url")
@click.option(
    "--source-type",
    type=click.Choice(["git", "tarball", "zip"]),
    required=True,
)
@click.option(
    "--dest",
    type=click.Path(),
    required=True,
    help="Destination directory for the acquired source.",
)
def acquire_source_cmd(origin_url: str, source_type: str, dest: str) -> None:
    """Acquire source into DEST.

    Clones a git repo or extracts a tarball/zip into the destination directory.
    Writes ActionResult JSON to stdout; exits non-zero on failure.
    """
    cmd = AcquireSourceCommand(
        args=AcquireSourceArgs(
            origin_url=origin_url,
            source_type=source_type,  # type: ignore[arg-type]
            dest=Path(dest),
        )
    )
    result = run_command(cmd, log=_make_log_sink(None))
    _emit_result(result)


# ================================================
# init-ree
# ================================================


@cli.command("init-ree")
@click.option("--ree-id", required=True, help="The REE identifier.")
@click.option("--name", default=None, help="Human-readable name for the REE.")
def init_ree_cmd(ree_id: str, name: str | None) -> None:
    """Initialise the REE directory structure at /ree.

    Creates the directory skeleton and writes an initial .workspace.json.
    Idempotent: exits 0 without modifying anything if already initialised.
    """
    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    if store.metadata_exists():
        click.echo(json.dumps({"status": "already_initialised", "reeId": ree_id}))
        return

    store.ensure_dirs()

    ts = _utc_now()
    ree_name = name or f"workspace-{ree_id[:8]}"
    metadata = {
        "reeId": ree_id,
        "externalRef": None,
        "name": ree_name,
        "status": "draft",
        "createdAt": ts,
        "updatedAt": ts,
        "reeIntent": ReeIntent(name=ree_name).model_dump(exclude_none=True),
        "reeSession": ReeSession().model_dump(exclude_none=True),
        "source": None,
    }

    store.write_metadata_json(metadata)
    click.echo(json.dumps({"status": "initialised", "reeId": ree_id}))


# ================================================
# get-ree
# ================================================


@cli.command("get-ree")
def get_ree_cmd() -> None:
    """Emit the current REE metadata as JSON.

    Reads .workspace.json from /ree. Exits non-zero if not initialised.
    """
    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    if not store.metadata_exists():
        click.echo(json.dumps({"error": "not initialised"}), file=sys.stderr)
        sys.exit(1)

    metadata = store.read_metadata_json()
    click.echo(json.dumps(metadata))


# ================================================
# get-workspace
# ================================================


@cli.command("get-workspace")
def get_workspace_cmd() -> None:
    """Emit full workspace state (metadata + file listings) as JSON.

    Equivalent to the host-side get_workspace() but executed inside the
    workbench container so the output reflects the workbench volume.
    """
    layout = ReeLayout.in_workbench()
    # workspace_ops uses (storage_root, ree_id) addressing; the workbench
    # volume is mounted at /ree, which maps to storage_root=/ and ree_id=ree.
    storage_root = layout.root.parent
    ree_id = layout.root.name
    try:
        result = _get_workspace(storage_root, ree_id)
    except FileNotFoundError as exc:
        click.echo(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    click.echo(json.dumps(result))


# ================================================
# build-archive
# ================================================


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


# ================================================
# Read
# ================================================


@cli.command("get-receipts")
def get_receipts_cmd() -> None:
    """Emit the receipts journal as a JSON array.

    Each element is a serialised ActionReceipt. Returns an empty array if no
    structural operations have been journaled yet.
    """
    layout = ReeLayout.in_workbench()
    receipts = ReceiptJournal(layout).read_all()
    click.echo(json.dumps([r.model_dump(mode="json") for r in receipts]))


@cli.command("read-file")
@click.option(
    "--path", "file_path", required=True, help="Relative path within workspace"
)
def read_file_cmd(file_path: str) -> None:
    """Write raw bytes of a workspace file to stdout."""
    layout = ReeLayout.in_workbench()
    storage_root = layout.root.parent
    ree_id = layout.root.name
    try:
        data = _read_file_bytes(storage_root, ree_id, file_path)
    except FileNotFoundError:
        click.echo(json.dumps({"error": f"not found: {file_path}"}), file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        click.echo(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    sys.stdout.buffer.write(data)


@cli.command("read-artifact")
@click.option(
    "--path", "artifact_path", required=True, help="Relative path within artifacts/"
)
def read_artifact_cmd(artifact_path: str) -> None:
    """Write raw bytes of an artifact file to stdout."""
    layout = ReeLayout.in_workbench()
    fp = layout.artifacts / artifact_path
    if not fp.exists() or not fp.is_file():
        click.echo(
            json.dumps({"error": f"not found: {artifact_path}"}), file=sys.stderr
        )
        sys.exit(1)
    sys.stdout.buffer.write(fp.read_bytes())


def _emit_result(result: ActionResult) -> None:
    click.echo(result.model_dump_json())
    if result.status != "succeeded":
        sys.exit(1)

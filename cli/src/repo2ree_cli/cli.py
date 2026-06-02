from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

import click

from repo2ree_core.domain.ree import REE
from repo2ree_core.envelope import ActionResult, command_adapter, run_command
from repo2ree_core.envelope.command import AcquireSourceArgs, AcquireSourceCommand
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore


# ------------------------------------------------
# Log sinks
# ------------------------------------------------


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


# ------------------------------------------------
# Root group
# ------------------------------------------------


@click.group()
def cli() -> None:
    """repo2ree — build and run reproducible execution environments."""


def main() -> None:
    cli()


# ------------------------------------------------
# execute  (envelope path — used by the dispatcher)
# ------------------------------------------------


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

    run_log: TextIO | None = None
    if run_id is not None:
        layout = ReeLayout.in_workbench()
        layout.runs.mkdir(parents=True, exist_ok=True)
        run_log = layout.run_log(run_id).open("a", encoding="utf-8")

    try:
        log = _make_log_sink(run_log)
        result = run_command(cmd, log=log, run_id=run_id or "manual")
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


# ------------------------------------------------
# acquire-source  (argv-sugar path)
# ------------------------------------------------


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


# ------------------------------------------------
# init-ree
# ------------------------------------------------


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
        "reeDraft": REE(name=ree_name).model_dump(exclude_none=True),
        "source": None,
    }
    store.write_metadata_json(metadata)
    click.echo(json.dumps({"status": "initialised", "reeId": ree_id}))


# ------------------------------------------------
# get-ree
# ------------------------------------------------


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


# ------------------------------------------------
# Helpers
# ------------------------------------------------


def _emit_result(result: ActionResult) -> None:
    click.echo(result.model_dump_json())
    if result.status != "succeeded":
        sys.exit(1)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

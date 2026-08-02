"""Record which durable inputs produced the current mutable workspace."""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.digests import digest_tree
from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import LogSink


def stat_table(workspace: Path) -> dict[str, list[int]]:
    """Return ``{relpath: [size, mtime_ns]}`` for regular workspace files."""
    if not workspace.is_dir():
        return {}
    table: dict[str, list[int]] = {}
    for path in sorted(workspace.rglob("*")):
        if path.is_file():
            stat = path.stat()
            table[path.relative_to(workspace).as_posix()] = [stat.st_size, stat.st_mtime_ns]
    return table


def record_materialization(
    layout: ReeLayout,
    *,
    snapshot_digest: str | None,
    log: LogSink,
) -> None:
    """Record the source, overlay, and workspace facts of a materialization."""
    try:
        marker = {
            "materialized_at": utc_now(),
            "snapshot_digest": snapshot_digest,
            "overlay_digest": digest_tree(layout.overlay),
            "files": stat_table(layout.workspace),
        }
        write_json_atomic(layout.materialize_marker, marker)
    except Exception as exc:  # noqa: BLE001 — marker failure degrades drift to unknown; it cannot fail the run
        log("system", "warn", f"failed to record workspace materialization: {exc}")

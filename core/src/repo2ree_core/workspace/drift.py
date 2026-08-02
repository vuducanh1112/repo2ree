"""Observe mutations in a materialized workspace against its durable inputs."""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path, PurePosixPath

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.experiment import Runnable
from repo2ree_core.domain.primitives import ReePath
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.receipt import WorkspaceDrift
from repo2ree_core.path_safety import WORKSPACE_CONTROL_PREFIXES
from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.workspace.materialization import stat_table

_DRIFT_PATHS_CAP = 20


def _is_control_name(relative: str) -> bool:
    return PurePosixPath(relative).name.startswith(WORKSPACE_CONTROL_PREFIXES)


def declared_output_paths(intent: ReeIntent) -> set[str]:
    """Workspace paths that executions legitimately rewrite."""
    paths = {intent.runtime} if intent.runtime else set()
    runnables: list[Runnable] = [intent.activation, *intent.experiments]
    for runnable in runnables:
        paths.update(runnable.output_paths)
    return paths


def check_workspace_drift(layout: ReeLayout, *, excluded_paths: set[str]) -> WorkspaceDrift:
    """Compare the mutable workspace with current ``upstream + overlay``."""
    if not layout.materialize_marker.is_file():
        return WorkspaceDrift(status="unknown")
    try:
        marker = json.loads(layout.materialize_marker.read_text(encoding="utf-8"))
        recorded: dict[str, list[int]] = dict(marker.get("files") or {})
    except Exception:  # noqa: BLE001 — an unreadable marker has the explicit unknown verdict
        return WorkspaceDrift(status="unknown")

    current = stat_table(layout.workspace)
    drifted: list[str] = []

    def expected_file(relative: str) -> Path | None:
        for base in (layout.overlay, layout.upstream):
            candidate = base / relative
            if candidate.is_file():
                return candidate
        return None

    for relative in sorted(set(recorded) | set(current)):
        if relative in excluded_paths or _is_control_name(relative) or recorded.get(relative) == current.get(relative):
            continue
        expected = expected_file(relative)
        actual = layout.workspace / relative
        if not actual.is_file():
            if expected is not None:
                drifted.append(relative)
            continue
        if expected is None or digest_file(actual) != digest_file(expected):
            drifted.append(relative)

    if not drifted:
        return WorkspaceDrift(status="clean")
    return WorkspaceDrift(
        status="modified",
        changed_paths=[ReePath(path) for path in drifted[:_DRIFT_PATHS_CAP]],
        changed_path_count=len(drifted),
    )


def current_runtime_digest(layout: ReeLayout, runtime_path: str | None) -> str | None:
    """Digest a runtime currently inside the workspace, with a stat-keyed cache."""
    if not runtime_path:
        return None
    path = layout.workspace / runtime_path
    if not path.is_file():
        return None
    stat = path.stat()
    key = {"path": runtime_path, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    with suppress(Exception):
        cached = json.loads(layout.digest_cache.read_text(encoding="utf-8"))
        if {name: cached.get(name) for name in key} == key and cached.get("digest"):
            return str(cached["digest"])
    digest = digest_file(path)
    with suppress(Exception):
        write_json_atomic(layout.digest_cache, {**key, "digest": digest})
    return digest

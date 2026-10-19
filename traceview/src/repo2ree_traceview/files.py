"""Read what a recording holds besides the checker's evidence: spans, its manifest, capture commit sizes."""

from __future__ import annotations

import json
import os
import subprocess
from importlib.resources import files
from pathlib import Path

from repo2ree_traceview.model import Recording
from repo2ree_traceview.spans import Span, parse_spans

TRACES = "traces.ndjson"
HISTORY_REF = "refs/heads/ree-history"


def read_spans(recording: Path) -> list[Span]:
    path = recording / TRACES
    return parse_spans(path.read_text()) if path.exists() else []


def read_recording(recording: Path) -> Recording:
    path = recording / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {}
    return Recording(
        name=recording.name,
        test=manifest.get("nodeid"),
        outcome=manifest.get("outcome"),
        revision=manifest.get("build_revision"),
    )


def commit_sizes(repositories: list[Path], executable: str = "git") -> dict[str, int]:
    """How many paths each capture commit changed, for display."""
    sizes: dict[str, int] = {}
    for repository in repositories:
        try:
            log = subprocess.run(
                [
                    executable,
                    "--no-pager",
                    "--git-dir",
                    str(repository / ".git"),
                    "log",
                    "--format=%x00%H",
                    "--name-only",
                    "--no-renames",
                    HISTORY_REF,
                    "--",
                ],
                capture_output=True,
                text=True,
                check=True,
                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            continue
        for entry in log.split("\0")[1:]:
            commit, *paths = entry.strip().splitlines()
            sizes[commit] = sum(1 for path in paths if path.strip())
    return sizes


def template() -> str:
    return (files("repo2ree_traceview") / "templates" / "operation_trace.html").read_text()

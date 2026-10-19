"""Read what a recording holds besides the checker's evidence: spans, its context, capture commit sizes."""

from __future__ import annotations

import os
import subprocess
from importlib.resources import files
from pathlib import Path

from repo2ree_conformance.recording import history_head
from repo2ree_recording import Recording as Manifest
from repo2ree_traceview.model import Recording
from repo2ree_traceview.spans import Span, parse_spans


def read_spans(recording: Path, manifest: Manifest) -> list[Span]:
    """Every spans file the manifest lists, one per process that exported them."""
    spans: list[Span] = []
    for source in manifest.recorded("spans"):
        path = recording / source.path
        if path.exists():
            spans.extend(parse_spans(path.read_text()))
    return spans


def describe(recording: Path, manifest: Manifest) -> Recording:
    context = manifest.context
    return Recording(name=recording.name, test=context.test, outcome=context.outcome, revision=manifest.build_revision)


def repositories(recording: Path, manifest: Manifest) -> list[Path]:
    return [recording / source.path for source in manifest.recorded("git")]


def commit_sizes(repositories: list[Path], executable: str = "git") -> dict[str, int]:
    """How many paths each capture commit changed, for display."""
    sizes: dict[str, int] = {}
    for repository in repositories:
        try:
            head, _ = history_head(executable, repository)
            if head is None:
                continue
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
                    head,
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

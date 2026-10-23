"""Read what a dossier holds besides the checker's evidence: spans, its context, capture commit sizes."""

from __future__ import annotations

import os
import subprocess
from importlib.resources import files
from pathlib import Path

from repo2ree_assurance_checker.dossier import history_head
from repo2ree_assurance_dossier import Dossier
from repo2ree_assurance_traceview.model import DossierInfo
from repo2ree_assurance_traceview.spans import Span, parse_spans


def read_spans(directory: Path, dossier: Dossier) -> list[Span]:
    """Every spans file the manifest lists, one per process that exported them."""
    spans: list[Span] = []
    for source in dossier.recorded("spans"):
        path = directory / source.path
        if path.exists():
            spans.extend(parse_spans(path.read_text()))
    return spans


def describe(directory: Path, dossier: Dossier) -> DossierInfo:
    context = dossier.context
    return DossierInfo(name=directory.name, test=context.test, outcome=context.outcome, revision=dossier.build_revision)


def repositories(directory: Path, dossier: Dossier) -> list[Path]:
    return [directory / source.path for source in dossier.recorded("git")]


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
    return (files("repo2ree_assurance_traceview") / "templates" / "behaviour_trace.html").read_text()

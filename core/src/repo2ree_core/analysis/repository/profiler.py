"""Repo profiler — impure orchestration layer.

Collects file signals, scans the manifests into a dependency inventory
(``sources/manifests.py`` — first-party parsers for the pypi/conda/oci
ecosystems), and delegates to the pure ``build_report`` function. This is the
single entry point callers use; a caller has no knowledge of which sources
are run.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path

from .reproducibility_report import (
    FileSignals,
    ReproducibilityReport,
    build_report,
    is_dockerfile_filename,
    is_manifest_filename,
    is_vm_artifact_filename,
)
from .sources.manifests import iter_workspace_files, scan_manifest_files

# ================================================
# Types
# ================================================

LogFn = Callable[[str, str, str], None]  # (stream, level, message)


# ================================================
# Exceptions
# ================================================


class AnalysisError(RuntimeError):
    """Raised when strict=True and the scan found no dependency data."""


# ================================================
# Entry point
# ================================================


def analyze_repo(
    repo_path: Path,
    log: LogFn | None = None,
    strict: bool = False,
) -> ReproducibilityReport:
    """Build the reproducibility report from the manifest scan and file signals.

    Raises ``AnalysisError`` when ``strict=True`` and the scan produced no
    per-dependency data at all.
    """
    if not repo_path.is_dir():
        raise ValueError(f"repo_path must be an existing directory: {repo_path}")

    _log: LogFn = log or (lambda *_: None)
    file_signals = _collect_file_signals(repo_path)
    inventory = scan_manifest_files(repo_path)
    _log(
        "system",
        "info",
        f"manifest scan found {len(inventory.dependencies)} dependency entries",
    )
    if strict and not inventory.dependencies:
        raise AnalysisError("strict evaluation requires dependency data, and the manifest scan found none")
    return build_report(inventory, file_signals)


# ================================================
# Internals
# ================================================


def _collect_file_signals(repo_path: Path) -> FileSignals:
    # Same pruned walk as the manifest scan: a manifest (or Dockerfile) inside
    # node_modules or a committed .venv must not count as the repo's own.
    signals = FileSignals()
    for file_path, _relative in iter_workspace_files(repo_path):
        lower_name = file_path.name.lower()
        if is_manifest_filename(lower_name):
            signals.has_manifest = True
        if is_dockerfile_filename(lower_name):
            signals.has_dockerfile = True
            with contextlib.suppress(OSError):
                signals.dockerfile_texts.append(file_path.read_text(encoding="utf-8", errors="replace"))
        if lower_name.endswith(".nix"):
            signals.has_nix_file = True
        if is_vm_artifact_filename(lower_name):
            signals.has_vm = True

    if signals.dockerfile_texts and not signals.has_dockerfile:
        raise AssertionError("dockerfile_texts populated without has_dockerfile flag")

    return signals

"""Repo profiler — impure orchestration layer.

Coordinates dependency analysis tool(s) and file-signal collection, then
delegates to the pure ``build_report`` function.  This is the single entry
point for the API layer; the API has no knowledge of which tools are run.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

from .reproducibility_report import (
    FileSignals,
    ReproducibilityReport,
    build_report,
    is_dockerfile_filename,
    is_manifest_filename,
    is_vm_artifact_filename,
)
from .sources.renovate import run_extract

# ================================================
# Types
# ================================================

LogFn = Callable[[str, str, str], None]  # (stream, level, message)


# ================================================
# Exceptions
# ================================================


class AnalysisError(RuntimeError):
    """Raised when strict=True and no dependency data could be extracted."""


# ================================================
# Entry point
# ================================================


def analyze_repo(
    repo_path: Path,
    log: LogFn | None = None,
    strict: bool = False,
) -> ReproducibilityReport:
    """Run dependency analysis and build the reproducibility report.

    Raises ``AnalysisError`` when ``strict=True`` and no dependency data could
    be extracted from any tool.
    """
    if not repo_path.is_dir():
        raise ValueError(f"repo_path must be an existing directory: {repo_path}")

    _log: LogFn = log or (lambda *_: None)
    file_signals = _collect_file_signals(repo_path)
    inventory = run_extract(repo_path, log=_log)
    if strict and inventory is None:
        raise AnalysisError("Dependency analysis produced no extractable output")
    return build_report(inventory, file_signals)


# ================================================
# Internals
# ================================================


def _collect_file_signals(repo_path: Path) -> FileSignals:
    signals = FileSignals()
    for file_path in _iter_files(repo_path):
        lower_name = file_path.name.lower()
        if is_manifest_filename(lower_name):
            signals.has_manifest = True
        if is_dockerfile_filename(lower_name):
            signals.has_dockerfile = True
            try:
                signals.dockerfile_texts.append(file_path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
        if lower_name.endswith(".nix"):
            signals.has_nix_file = True
        if is_vm_artifact_filename(lower_name):
            signals.has_vm = True

    if signals.dockerfile_texts and not signals.has_dockerfile:
        raise AssertionError("dockerfile_texts populated without has_dockerfile flag")

    return signals


def _iter_files(repo_path: Path) -> Iterator[Path]:
    for file_path in sorted(repo_path.rglob("*")):
        if file_path.is_file():
            yield file_path

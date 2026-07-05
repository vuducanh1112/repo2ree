"""Repo profiler — impure orchestration layer.

Collects file signals and delegates to the pure ``build_report`` function.
This is the single entry point for the API layer; the API has no knowledge of
which tools are run.

Dependency *extraction* is currently retired: the renovate flow was dropped
(node-runtime weight, freshness coupling — see ``sources/renovate.py``, kept
as a dormant parser for the future extraction-adapter comparison), and its
successor (a syft-backed inventory source) is not built yet. Until it is, the
report scores on file signals alone (manifest/lockfile/Dockerfile/nix/VM
presence — pure filesystem checks) with an empty dependency inventory.
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

# ================================================
# Types
# ================================================

LogFn = Callable[[str, str, str], None]  # (stream, level, message)


# ================================================
# Exceptions
# ================================================


class AnalysisError(RuntimeError):
    """Raised when strict=True and no dependency data is available."""


# ================================================
# Entry point
# ================================================


def analyze_repo(
    repo_path: Path,
    log: LogFn | None = None,
    strict: bool = False,
) -> ReproducibilityReport:
    """Build the reproducibility report from file signals.

    Raises ``AnalysisError`` when ``strict=True`` — with extraction retired
    there is never per-dependency data, which is exactly what strict demands.
    """
    if not repo_path.is_dir():
        raise ValueError(f"repo_path must be an existing directory: {repo_path}")

    _log: LogFn = log or (lambda *_: None)
    _log(
        "system",
        "info",
        "dependency extraction is retired pending the next analyzer; scoring on file signals only",
    )
    file_signals = _collect_file_signals(repo_path)
    if strict:
        raise AnalysisError("strict evaluation requires dependency extraction, which is currently retired")
    return build_report(None, file_signals)


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

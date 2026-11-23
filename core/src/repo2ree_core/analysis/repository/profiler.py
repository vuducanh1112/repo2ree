from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path

from repo2ree_ree.reproducibility import ReproducibilityReport

from .reproducibility_report import (
    FileSignals,
    build_report,
    is_dockerfile_filename,
    is_manifest_filename,
    is_vm_artifact_filename,
)
from .sources.manifests import iter_workspace_files, scan_manifest_files

LogFn = Callable[[str, str, str], None]


class AnalysisError(RuntimeError):
    pass


def analyze_repo(
    repo_path: Path,
    log: LogFn | None = None,
    strict: bool = False,
) -> ReproducibilityReport:
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


def _collect_file_signals(repo_path: Path) -> FileSignals:
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

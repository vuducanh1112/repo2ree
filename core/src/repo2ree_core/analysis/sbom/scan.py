from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo2ree_core.execution.process import CancelCheck, format_command, run_streaming_process
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.tools import resolve_tool

SBOM_FORMAT = "cyclonedx-json"

EXPERIMENT_ENVIRONMENT_ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tgz")

CATALOGERS = "image"

SOURCES = ("docker-archive", "oci-archive", "file")


@dataclass(frozen=True)
class ScanOutcome:
    returncode: int | None
    tool_version: str | None = None
    canceled: bool = False
    source_kind: str | None = None


def is_experiment_environment_archive(path: str) -> bool:
    return path.lower().endswith(EXPERIMENT_ENVIRONMENT_ARCHIVE_SUFFIXES)


def scan_experiment_environment_archive(
    experiment_environment_abs: Path,
    output_path: Path,
    *,
    log: LogSink,
    is_canceled: CancelCheck = lambda: False,
) -> ScanOutcome:
    syft = resolve_tool("syft")
    argv = [
        syft,
        str(experiment_environment_abs),
        *(arg for source in SOURCES for arg in ("--from", source)),
        "--scope",
        "squashed",
        "--override-default-catalogers",
        CATALOGERS,
        "-o",
        f"{SBOM_FORMAT}={output_path}",
    ]
    log("system", "info", format_command(argv))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_streaming_process(argv, log=log, is_canceled=is_canceled)
    if result.canceled or is_canceled():
        return ScanOutcome(returncode=result.returncode, canceled=True)
    if result.returncode != 0:
        return ScanOutcome(returncode=result.returncode)
    source_kind = read_source_kind(output_path)
    log("system", "info", f"Scanned the experiment environment as: {source_kind or 'unknown'}")
    return ScanOutcome(returncode=0, tool_version=read_tool_version(output_path), source_kind=source_kind)


def read_source_kind(sbom_path: Path) -> str | None:
    metadata = _metadata(sbom_path)
    component = metadata.get("component") if metadata else None
    kind = component.get("type") if isinstance(component, dict) else None
    return kind if isinstance(kind, str) else None


def read_tool_version(sbom_path: Path) -> str | None:
    metadata = _metadata(sbom_path)
    tools = metadata.get("tools") if metadata else None
    entries = tools.get("components") if isinstance(tools, dict) else tools
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == "syft":
            version = entry.get("version")
            return version if isinstance(version, str) else None
    return None


def _metadata(sbom_path: Path) -> dict[str, Any] | None:
    try:
        data: Any = json.loads(sbom_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    metadata = data.get("metadata") if isinstance(data, dict) else None
    return metadata if isinstance(metadata, dict) else None

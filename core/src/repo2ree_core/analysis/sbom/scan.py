"""Running the SBOM scanner over a built runtime archive.

Shared by the author-side ``generate_sbom`` handler and the reviewer-side build
reproduction. Both sides must mean exactly the same thing by "observed in the
runtime" — otherwise an SBOM comparison measures the scanner, not the build —
so the tool, its scope, and the output format are pinned here once rather than
spelled at each call site.

Shell module: it runs a subprocess and writes the scanner's output file. The
parsing of that output into the IR stays in :mod:`repo2ree_core.analysis.sbom.cyclonedx`.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo2ree_core.execution.tools import resolve_tool
from repo2ree_protocol.log import LogSink

# The one format both the cross-check and the reviewer comparison parse.
SBOM_FORMAT = "cyclonedx-json"

# Scanning consumes a docker-archive tarball, never a live image.
RUNTIME_ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tgz")


@dataclass(frozen=True)
class ScanOutcome:
    """What a scan run produced: its exit code and the tool that produced it."""

    returncode: int
    tool_version: str | None = None


def is_runtime_archive(path: str) -> bool:
    """Whether a declared runtime path is a tarball the scanner can consume."""
    return path.lower().endswith(RUNTIME_ARCHIVE_SUFFIXES)


def scan_runtime_archive(runtime_abs: Path, output_path: Path, *, log: LogSink) -> ScanOutcome:
    """Scan a runtime tarball into a CycloneDX document at ``output_path``.

    ``--scope squashed`` is pinned explicitly: "observed in the runtime" must
    mean the squashed filesystem, and scanner defaults must not drift underneath
    the recorded evidence. A non-zero return code is reported, never raised —
    the caller decides whether a failed scan is fatal or merely inconclusive.
    """
    syft = resolve_tool("syft")
    argv = [
        syft,
        f"docker-archive:{runtime_abs}",
        "--scope",
        "squashed",
        "-o",
        f"{SBOM_FORMAT}={output_path}",
    ]
    log("system", "info", f"$ {' '.join(argv)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(argv, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        log("stdout", "info", line)
    for line in result.stderr.splitlines():
        log("stdout", "info", line)
    if result.returncode != 0:
        return ScanOutcome(returncode=result.returncode)
    return ScanOutcome(returncode=0, tool_version=read_tool_version(output_path))


def read_tool_version(sbom_path: Path) -> str | None:
    """The generating syft version out of a written CycloneDX document.

    ``metadata.tools`` is a ``{"components": [...]}`` object on CycloneDX >= 1.5
    and a bare list of tool objects on 1.4; absence is not an error, and neither
    is an unreadable document — the version is provenance, not a result.
    """
    try:
        data: Any = json.loads(sbom_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    tools = (data.get("metadata") or {}).get("tools")
    entries = tools.get("components") if isinstance(tools, dict) else tools
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == "syft":
            version = entry.get("version")
            return version if isinstance(version, str) else None
    return None

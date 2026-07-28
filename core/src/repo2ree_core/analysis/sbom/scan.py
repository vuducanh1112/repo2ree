"""Running the SBOM scanner over a built runtime archive.

Shared by the author-side ``generate_sbom`` handler and the reviewer-side build
reproduction. Both sides must mean exactly the same thing by "observed in the
runtime" — otherwise an SBOM comparison measures the scanner, not the build —
so the tool, its scope, and the output format are pinned here once rather than
spelled at each call site.

Shell module: it runs a subprocess and writes the scanner's output file. The
parsing of that output into the IR stays in :mod:`repo2ree_core.analysis.sbom.cyclonedx`.

The scan runs through the shared process runner rather than a blocking
``subprocess.run``. Scanning a multi-gigabyte runtime tarball is the longest
non-script operation in the system, and going through the runner is what makes
it behave like one: progress reaches the run log while it happens, a cancel
signals the whole process group instead of being noticed once the tool has
already finished, and the invocation lands on a ``workbench.exec`` span like
every other subprocess the workbench runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo2ree_core.execution.process import CancelCheck, format_command, run_streaming_process
from repo2ree_core.execution.tools import resolve_tool
from repo2ree_protocol.log import LogSink

# The one format both the cross-check and the reviewer comparison parse.
SBOM_FORMAT = "cyclonedx-json"

# Scanning consumes a docker-archive tarball, never a live image.
RUNTIME_ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tgz")


@dataclass(frozen=True)
class ScanOutcome:
    """What a scan run produced: how it ended, and the tool that produced it.

    ``canceled`` is its own field rather than a distinguished exit code: a
    scanner killed by a cancel exits nonzero the same way a scanner that choked
    on the archive does, and only one of those is news about the runtime.
    """

    returncode: int | None
    tool_version: str | None = None
    canceled: bool = False


def is_runtime_archive(path: str) -> bool:
    """Whether a declared runtime path is a tarball the scanner can consume."""
    return path.lower().endswith(RUNTIME_ARCHIVE_SUFFIXES)


def scan_runtime_archive(
    runtime_abs: Path,
    output_path: Path,
    *,
    log: LogSink,
    is_canceled: CancelCheck = lambda: False,
) -> ScanOutcome:
    """Scan a runtime tarball into a CycloneDX document at ``output_path``.

    ``--scope squashed`` is pinned explicitly: "observed in the runtime" must
    mean the squashed filesystem, and scanner defaults must not drift underneath
    the recorded evidence. Neither a non-zero return code nor a cancel is raised
    — both are reported, and the caller decides whether a scan that did not
    finish is fatal or merely leaves the evidence inconclusive.

    The scanner writes ``output_path`` itself, so a run that did not succeed can
    leave a partial document there. Callers that publish the result as durable
    evidence scan into a staging path and promote it only on success.
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
    log("system", "info", format_command(argv))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_streaming_process(argv, log=log, is_canceled=is_canceled)
    if result.canceled or is_canceled():
        return ScanOutcome(returncode=result.returncode, canceled=True)
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

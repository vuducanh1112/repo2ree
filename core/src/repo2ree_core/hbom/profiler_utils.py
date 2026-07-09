from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_GIB = 1024**3


def round_gib(value_bytes: int | float) -> float:
    if value_bytes <= 0:
        return 0.0
    gib = round(float(value_bytes) / _GIB, 2)

    # ── postcondition ──
    # A capacity is never negative; every HBOM definition treats this as a
    # non-negative quantity (the pydantic fields all carry ``ge=0``).
    assert gib >= 0.0, f"negative capacity: {gib}"  # noqa: S101
    # ───────────────────
    return gib


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def read_optional_text(path: str | Path) -> str:
    try:
        return read_text(path)
    except OSError:
        return ""


def read_optional_int(path: str | Path) -> int | None:
    value = read_optional_text(path)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def run_command(*args: str, timeout: int = 10) -> subprocess.CompletedProcess[str] | None:
    if not shutil.which(args[0]):
        return None
    try:
        return subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

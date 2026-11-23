from __future__ import annotations

import re

_EPOCH_RE = re.compile(r"^\d+[!:]")


def normalize_version(version: str) -> str:
    normalized = version.strip().lower().removeprefix("v")
    return _EPOCH_RE.sub("", normalized)


def versions_match(expected: str, observed: str) -> bool:
    return normalize_version(expected) == normalize_version(observed)

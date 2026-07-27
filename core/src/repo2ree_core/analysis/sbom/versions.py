"""Version-string comparison shared by every SBOM join.

Both SBOM joins ask the same question of two version strings — "are these the
same version?" — and must answer it identically: the declared-vs-observed
cross-check and the author-vs-reviewer closure comparison would otherwise
disagree about the very same pair of packages.

Pure leaf module: strings in, booleans out, no imports from the rest of core.
"""

from __future__ import annotations

import re

# ``N!`` (PEP 440) / ``N:`` (deb, conda) epoch prefixes — packaging metadata,
# not identity, for the exact-match comparisons done here.
_EPOCH_RE = re.compile(r"^\d+[!:]")


def normalize_version(version: str) -> str:
    """A version string reduced to the form the comparisons key on."""
    normalized = version.strip().lower().removeprefix("v")
    return _EPOCH_RE.sub("", normalized)


def versions_match(expected: str, observed: str) -> bool:
    """Whether two version strings name the same version."""
    return normalize_version(expected) == normalize_version(observed)

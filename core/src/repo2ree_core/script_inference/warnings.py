"""The stable warning catalog.

Warning *meaning* must not live only in prose or shell comments: the API
returns stable codes with a severity and a ``blocking`` flag so a machine can
enforce automation policy without parsing text. This module is the single
mapping from code to its fixed severity/blocking/message, so a leaf that names a
code cannot invent a new meaning for it.

Only the codes Phase 1 (build) can actually emit are defined here; the rest of
the design's reserved vocabulary is added as the strategy that raises it lands.
"""

from __future__ import annotations

from collections.abc import Sequence

from repo2ree_core.script_inference.models import InferenceWarning, WarningSeverity

_CATALOG: dict[str, tuple[WarningSeverity, bool, str]] = {
    "execution_not_validated": (
        "info",
        False,
        "This script has been inferred but not yet validated by execution.",
    ),
    "multiple_dockerfiles": (
        "error",
        True,
        "More than one Dockerfile sits at the logical project root; repo2ree will not guess which one is the runtime.",
    ),
    "ambiguous_build_context": (
        "error",
        True,
        "A Dockerfile was found below the logical project root, but its build "
        "context cannot be determined without explicit evidence.",
    ),
    "runtime_declaration_missing": (
        "warning",
        True,
        "No runtime artifact path is declared on the REE intent; set it before "
        "the build candidate can be considered complete.",
    ),
    "runtime_outside_project_root": (
        "error",
        True,
        "The declared runtime artifact path escapes the logical project root.",
    ),
    "pip_environment_strategy": (
        "info",
        False,
        "Builds a Python virtual environment from requirements.txt with pip and packs it as the "
        "runtime artifact — no container. Confirm this strategy before writing.",
    ),
    "python_version_unknown": (
        "warning",
        False,
        "requirements.txt does not declare a Python interpreter version, so the build uses the workbench's python.",
    ),
    "dependencies_not_locked": (
        "warning",
        False,
        "requirements.txt is not a lockfile; a future install may resolve different transitive versions.",
    ),
}


def make_warning(code: str, *, affected_paths: Sequence[str] = ()) -> InferenceWarning:
    """Build a structured warning from a catalog code.

    Raises ``KeyError`` for an unknown code so a leaf can never emit an
    uncatalogued warning — the registry's DAG validation relies on this.
    """
    severity, blocking, message = _CATALOG[code]
    return InferenceWarning(
        code=code,
        severity=severity,
        blocking=blocking,
        message=message,
        affected_paths=list(affected_paths),
    )


def is_known_code(code: str) -> bool:
    return code in _CATALOG

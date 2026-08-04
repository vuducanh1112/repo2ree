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

from repo2ree_core.author_recipes.inference.models import InferenceWarning, WarningSeverity

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
    # --- runtime contract (activation / experiment) ---
    "runtime_not_resolved": (
        "error",
        True,
        "No runtime contract could be resolved, so the runtime plumbing cannot be generated.",
    ),
    "runtime_artifact_missing": (
        "error",
        True,
        "The declared runtime artifact does not exist yet; build the runtime before generating this script.",
    ),
    "runtime_archive_invalid": (
        "error",
        True,
        "The declared runtime artifact is not a readable archive of a recognized runtime kind.",
    ),
    "runtime_image_ref_missing": (
        "error",
        True,
        "The runtime archive declares no usable image reference, so no image can be loaded and run.",
    ),
    "multiple_runtime_images": (
        "error",
        True,
        "The runtime archive declares more than one image reference; repo2ree will not guess which is the runtime.",
    ),
    "venv_restore_dir_assumed": (
        "warning",
        True,
        "The packed venv does not record the directory it was built in, so it will be restored to the "
        "default location; if it was built elsewhere, restoration will fail — confirm VENV_DIR in the "
        "generated script points at the path the venv was built at before running.",
    ),
    # --- activation / experiment command ---
    "activation_command_missing": (
        "warning",
        True,
        "No activation command was selected; edit the 'set --' line to define a finite command that "
        "proves the runtime is usable before running activation.",
    ),
    "experiment_command_missing": (
        "warning",
        True,
        "No experiment command was selected; edit the 'set --' line to define the command whose result "
        "you intend to preserve before running the experiment.",
    ),
    "experiment_not_declared": (
        "error",
        True,
        "The requested experiment is not declared on the REE; declare it before generating its run script.",
    ),
    "experiment_output_declaration_missing": (
        "warning",
        True,
        "The generated log path is not among the experiment's declared output_paths; declare it so the "
        "result is captured and disclosed.",
    ),
    "possibly_long_running": (
        "info",
        False,
        "A detected candidate command may start a server or run indefinitely; confirm it is finite before use.",
    ),
    "shell_required_in_runtime": (
        "info",
        False,
        "A detected candidate is a shell-form command; it is offered verbatim and needs a shell in the "
        "runtime (make it explicit with 'set -- sh -c ...').",
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

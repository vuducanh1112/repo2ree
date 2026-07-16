"""Reserved, REE-owned script paths (the ``ree-scripts/`` overlay namespace).

Leaf module: it imports nothing from ``repo2ree_core`` so the domain,
experiment, and storage layers can all share these constants without an import
cycle (``storage`` → ``domain`` → ``experiment`` would otherwise close a loop).

REE-owned scripts live under a dedicated ``ree-scripts/`` directory so REE's
own recipe files (named with common names like ``build_script.sh``) can never
clash with — or silently shadow — a project's same-named source files when
upstream and overlay are merged into ``workspace/``. The author edits concepts
such as "Build" and "Activation", not storage paths. The directory is *not*
named ``ree``: inside a tree already rooted at ``/ree`` that read as
``/ree/overlay/ree/…``, giving the word three meanings at once.
"""

from __future__ import annotations

RESERVED_SCRIPT_DIR = "ree-scripts"

# The mandatory runtime build script: produces the runtime artifact.
RESERVED_BUILD_SCRIPT = f"{RESERVED_SCRIPT_DIR}/build_script.sh"
# Activation is the designated runnable that proves the built runtime is
# inhabitable. Experiments own their own per-experiment scripts under
# ``ree-scripts/experiments/``, created on demand rather than seeded here: a run
# script ``<slug>.sh`` and an optional verify script ``<slug>.verify.sh``.
RESERVED_ACTIVATION_SCRIPT = f"{RESERVED_SCRIPT_DIR}/activation.sh"
# Activation's optional verify script lives beside its run script. Unlike the
# run script it is not seeded: a declared verify script must exist and pass, so
# declaring one is an authoring act.
RESERVED_ACTIVATION_VERIFY_SCRIPT = f"{RESERVED_SCRIPT_DIR}/activation.verify.sh"
RESERVED_EXPERIMENT_SCRIPT_DIR = f"{RESERVED_SCRIPT_DIR}/experiments"

# Scripts seeded into a fresh REE's overlay on creation.
RESERVED_OVERLAY_SCRIPTS = (
    RESERVED_BUILD_SCRIPT,
    RESERVED_ACTIVATION_SCRIPT,
)


def experiment_slug(name: str) -> str:
    """The path-safe slug an experiment's reserved script names derive from.

    Experiment names are already constrained to path-safe characters (see
    ``experiment.EXPERIMENT_NAME_PATTERN``); whitespace collapses to hyphens so
    the path stays tidy.
    """
    return "-".join(str(name or "").split()) or "experiment"


def experiment_run_script_path(name: str) -> str:
    """The reserved run-script path for an experiment name."""
    return f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{experiment_slug(name)}.sh"


def experiment_verify_script_path(name: str) -> str:
    """The reserved verify-script path for an experiment name."""
    return f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{experiment_slug(name)}.verify.sh"

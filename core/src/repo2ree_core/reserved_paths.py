"""Reserved, REE-owned script paths (the ``ree/`` overlay namespace).

Leaf module: it imports nothing from ``repo2ree_core`` so the domain,
experiment, and storage layers can all share these constants without an import
cycle (``storage`` → ``domain`` → ``experiment`` would otherwise close a loop).

REE-owned scripts live under a dedicated ``ree/`` directory so REE's own recipe
files (named with common names like ``build_script.sh``) can never clash with —
or silently shadow — a project's same-named source files when upstream and
overlay are merged into ``workspace/``. The author edits concepts such as
"Build" and "Activation", not storage paths.
"""

from __future__ import annotations

RESERVED_SCRIPT_DIR = "ree"

# The mandatory runtime build script: produces the runtime artifact.
RESERVED_BUILD_SCRIPT = f"{RESERVED_SCRIPT_DIR}/build_script.sh"
# Activation is the designated runnable that proves the built runtime is
# inhabitable. Experiments own their own per-experiment scripts under
# ``ree/experiments/``, created on demand rather than seeded here: a run
# script ``<slug>.sh`` and an optional verify script ``<slug>.verify.sh``.
RESERVED_ACTIVATION_SCRIPT = f"{RESERVED_SCRIPT_DIR}/activation.sh"
RESERVED_EXPERIMENT_SCRIPT_DIR = f"{RESERVED_SCRIPT_DIR}/experiments"

# Scripts seeded into a fresh REE's overlay on creation.
RESERVED_OVERLAY_SCRIPTS = (
    RESERVED_BUILD_SCRIPT,
    RESERVED_ACTIVATION_SCRIPT,
)

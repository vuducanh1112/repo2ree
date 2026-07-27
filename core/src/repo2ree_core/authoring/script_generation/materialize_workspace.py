"""The generated ``materialize_workspace.sh`` — the single, shared merge muscle.

Materializing a workspace means *assembling a clean execution view* from the two
sources of truth: the acquired ``upstream/`` source and the author ``overlay/``,
with the overlay winning on conflict. The workspace is derived and disposable,
so it is cleared first — a re-materialize always starts from a deterministic
slate. This one merge serves both phases:

* authoring  → run in the workbench after acquisition folds the upstream source
  into the workspace (incremental overlay edits are mirrored live by the
  write/delete handlers; this is the full rebuild at pipeline boundaries);
* reproduction → called by ``run.sh`` between ``acquire`` and the runtime restore.

The upstream, overlay, and workspace dirs are fixed by REE layout, derived from
the script's own directory, so the same script runs unchanged in the workbench
(authoring) and inside a sealed bundle (reproduction, called by ``run.sh``).

Pure merge muscle: acquiring the source and restoring the sealed runtime are the
caller's job (a separate authoring step; ``run.sh`` orchestration at reproduction).

Pure module: it builds bytes from values and performs no I/O. The generated
bytes are deterministic given their inputs.
"""

from __future__ import annotations

from repo2ree_core.authoring.script_generation.shell import assert_no_placeholders, shell_single_quote, shell_text
from repo2ree_core.ree.layout import OVERLAY_DIRNAME, UPSTREAM_DIRNAME, WORKSPACE_DIRNAME

# The ``@@...@@`` tokens are the interpolation points for the layout dirnames,
# so the shell function bodies keep their literal braces unescaped.
_TEMPLATE = shell_text("""
    #!/bin/sh
    # repo2ree materialize-workspace — generated. Assembles a clean workspace as the
    # merge of the acquired upstream source and the author overlay (overlay wins).
    set -eu

    UPSTREAM_DIRNAME=@@UPSTREAM_DIRNAME@@
    OVERLAY_DIRNAME=@@OVERLAY_DIRNAME@@
    WORKSPACE_DIRNAME=@@WORKSPACE_DIRNAME@@

    REE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    upstream="$REE_ROOT/$UPSTREAM_DIRNAME"
    overlay="$REE_ROOT/$OVERLAY_DIRNAME"
    workspace="$REE_ROOT/$WORKSPACE_DIRNAME"

    say() { printf '%s\\n' "$*"; }
    usage() { echo "usage: $0" >&2; exit 2; }

    [ $# -eq 0 ] || usage

    # Derived and disposable: reset so each materialize starts from a clean slate.
    rm -rf "$workspace"; mkdir -p "$workspace"

    # upstream first, then overlay on top so the overlay wins on conflict. Both
    # arms are guarded: an overlay-only source has an empty upstream, and a bundle
    # with no author files has no overlay dir.
    if [ -d "$upstream" ] && [ -n "$(ls -A "$upstream" 2>/dev/null)" ]; then
      ( cd "$upstream" && tar -cf - . ) | ( cd "$workspace" && tar -xf - )
    fi
    if [ -d "$overlay" ]; then
      ( cd "$overlay" && tar -cf - . ) | ( cd "$workspace" && tar -xf - )
    fi

    say "Materialized clean workspace at $WORKSPACE_DIRNAME/"
""")


def build_materialize_sh() -> bytes:
    """Render the self-contained ``materialize_workspace.sh``.

    Takes no per-source inputs: the merge reads whatever is on disk under the
    fixed REE layout dirs at run time, so the same bytes serve every REE. The
    script accepts no arguments.
    """
    script = (
        _TEMPLATE.replace("@@UPSTREAM_DIRNAME@@", shell_single_quote(UPSTREAM_DIRNAME))
        .replace("@@OVERLAY_DIRNAME@@", shell_single_quote(OVERLAY_DIRNAME))
        .replace("@@WORKSPACE_DIRNAME@@", shell_single_quote(WORKSPACE_DIRNAME))
    )
    script = assert_no_placeholders(script, artifact="materialize_workspace.sh")
    return script.encode("utf-8")

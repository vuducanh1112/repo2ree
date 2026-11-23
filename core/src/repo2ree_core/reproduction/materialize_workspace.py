from __future__ import annotations

from repo2ree_core.persistence.layout import OVERLAY_DIRNAME, UPSTREAM_DIRNAME, WORKSPACE_DIRNAME
from repo2ree_core.reproduction.shell import assert_no_placeholders, shell_single_quote, shell_text

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
    script = (
        _TEMPLATE.replace("@@UPSTREAM_DIRNAME@@", shell_single_quote(UPSTREAM_DIRNAME))
        .replace("@@OVERLAY_DIRNAME@@", shell_single_quote(OVERLAY_DIRNAME))
        .replace("@@WORKSPACE_DIRNAME@@", shell_single_quote(WORKSPACE_DIRNAME))
    )
    script = assert_no_placeholders(script, artifact="materialize_workspace.sh")
    return script.encode("utf-8")

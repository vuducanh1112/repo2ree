from __future__ import annotations

from repo2ree_core.persistence.layout import SNAPSHOT_FILENAME, UPSTREAM_DIRNAME
from repo2ree_core.reproduction.shell import assert_no_placeholders, shell_single_quote, shell_text

_TEMPLATE = shell_text("""
    #!/bin/sh
    # repo2ree acquire-source — generated. Populates an upstream directory from the
    # frozen snapshot, or by fetching the recorded origin and verifying its SWHID.
    set -eu

    ORIGIN_URL=@@ORIGIN_URL@@
    SWHID=@@SWHID@@
    UPSTREAM_DIRNAME=@@UPSTREAM_DIRNAME@@
    SNAPSHOT_FILENAME=@@SNAPSHOT_FILENAME@@

    REE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    upstream="$REE_ROOT/$UPSTREAM_DIRNAME"
    snapshot="$REE_ROOT/$SNAPSHOT_FILENAME"

    say() { printf '%s\\n' "$*"; }
    die() { printf 'error: %s\\n' "$*" >&2; exit 1; }
    usage() { echo "usage: $0 [--refetch]" >&2; exit 2; }

    REFETCH=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --refetch) REFETCH=1 ;;
        *) usage ;;
      esac
      shift
    done

    # Best-effort source-identity check. The fetch already happened; a local machine
    # may lack the `swh` tool, so a missing tool — or a mismatch — only warns.
    verify_swhid() {
      dir=$1
      [ -n "$SWHID" ] || { say "No recorded SWHID; source identity not verified."; return 0; }
      if command -v swh >/dev/null 2>&1; then
        actual=$(swh identify --no-filename "$dir" 2>/dev/null || true)
        if printf '%s' "$actual" | grep -qF "$SWHID"; then
          say "Source identity verified against SWHID."
        else
          say "WARNING: source SWHID mismatch (recorded $SWHID, got ${actual:-none}) — reproduction may differ."
        fi
      else
        say "WARNING: 'swh' not installed; fetched source but could not verify against $SWHID."
      fi
    }

    @@FETCH_SOURCE@@

    # Idempotent: a populated upstream is left alone unless a re-fetch was asked for.
    if [ "$REFETCH" -eq 0 ] && [ -d "$upstream" ] && [ -n "$(ls -A "$upstream" 2>/dev/null)" ]; then
      say "upstream already populated; nothing to do."
      exit 0
    fi

    rm -rf "$upstream"; mkdir -p "$upstream"

    if [ "$REFETCH" -eq 1 ] && [ -n "$ORIGIN_URL" ]; then
      fetch_source "$upstream"
      verify_swhid "$upstream"
    elif [ -f "$snapshot" ]; then
      say "Extracting frozen snapshot (identity sealed in)."
      tar -xzf "$snapshot" -C "$upstream"
    elif [ -n "$ORIGIN_URL" ]; then
      fetch_source "$upstream"
      verify_swhid "$upstream"
    else
      say "WARNING: no snapshot at $snapshot and no origin recorded — leaving upstream empty (overlay-only)."
    fi
""")


def _fetch_source_function(source_type: str, revision: str) -> str:
    if source_type == "git":
        if revision:
            return shell_text("""
                fetch_source() {
                  dest=$1
                  rev=@@REVISION@@
                  [ -n "$ORIGIN_URL" ] || die "no origin recorded; cannot fetch"
                  command -v git >/dev/null 2>&1 || die "git is required to fetch this source"
                  say "Fetching source from $ORIGIN_URL (git, pinned to $rev)"
                  git init -q "$dest"
                  git -C "$dest" remote add origin "$ORIGIN_URL"
                  if git -C "$dest" fetch -q --depth 1 origin "$rev" 2>/dev/null; then
                    git -C "$dest" checkout -q FETCH_HEAD
                  else
                    say "shallow fetch of $rev rejected; falling back to full clone"
                    git -C "$dest" fetch -q origin
                    git -C "$dest" checkout -q "$rev"
                  fi
                }
            """).replace("@@REVISION@@", shell_single_quote(revision))
        return shell_text("""
            fetch_source() {
              dest=$1
              [ -n "$ORIGIN_URL" ] || die "no origin recorded; cannot fetch"
              command -v git >/dev/null 2>&1 || die "git is required to fetch this source"
              say "Fetching source from $ORIGIN_URL (git)"
              git clone --depth 1 "$ORIGIN_URL" "$dest"
            }
        """)

    if source_type == "tarball":
        return shell_text("""
            fetch_source() {
              dest=$1
              [ -n "$ORIGIN_URL" ] || die "no origin recorded; cannot fetch"
              say "Fetching source from $ORIGIN_URL (tarball)"
              command -v tar >/dev/null 2>&1 || die "tar is required to fetch this source"
              if [ -f "$ORIGIN_URL" ]; then
                tar -xf "$ORIGIN_URL" -C "$dest"
              else
                command -v curl >/dev/null 2>&1 || die "curl is required to fetch this source"
                tmp=$(mktemp)
                trap 'rm -f "$tmp"' EXIT HUP INT TERM
                curl -fsSL "$ORIGIN_URL" -o "$tmp"
                tar -xf "$tmp" -C "$dest"
                rm -f "$tmp"
                trap - EXIT HUP INT TERM
              fi
            }
        """)

    if source_type == "zip":
        return shell_text("""
            fetch_source() {
              dest=$1
              [ -n "$ORIGIN_URL" ] || die "no origin recorded; cannot fetch"
              say "Fetching source from $ORIGIN_URL (zip)"
              command -v unzip >/dev/null 2>&1 || die "unzip is required to fetch this source"
              if [ -f "$ORIGIN_URL" ]; then
                unzip -q "$ORIGIN_URL" -d "$dest"
              else
                command -v curl >/dev/null 2>&1 || die "curl is required to fetch this source"
                tmp=$(mktemp)
                trap 'rm -f "$tmp"' EXIT HUP INT TERM
                curl -fsSL "$ORIGIN_URL" -o "$tmp"
                unzip -q "$tmp" -d "$dest"
                rm -f "$tmp"
                trap - EXIT HUP INT TERM
              fi
            }
        """)

    if source_type:
        message = f"cannot fetch source: unknown source_type {source_type!r}"
    else:
        message = "no origin recorded; cannot fetch"
    return shell_text("""
        fetch_source() {
          die @@MESSAGE@@
        }
    """).replace("@@MESSAGE@@", shell_single_quote(message))


def build_acquire_sh(*, origin_url: str = "", source_type: str = "", revision: str = "", swhid: str = "") -> bytes:
    script = (
        _TEMPLATE.replace("@@ORIGIN_URL@@", shell_single_quote(origin_url))
        .replace("@@SWHID@@", shell_single_quote(swhid))
        .replace("@@UPSTREAM_DIRNAME@@", shell_single_quote(UPSTREAM_DIRNAME))
        .replace("@@SNAPSHOT_FILENAME@@", shell_single_quote(SNAPSHOT_FILENAME))
        .replace("@@FETCH_SOURCE@@", _fetch_source_function(source_type, revision).rstrip())
    )
    script = assert_no_placeholders(script, artifact="acquire_source.sh")
    return script.encode("utf-8")

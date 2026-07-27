"""Shared shell-rendering helpers.

Runtime constants (the image reference, the runtime-artifact path) are derived
the same way for every build strategy so downstream scripts stay consistent and
the bytes stay deterministic — no timestamps, no per-call entropy.

The runtime artifact always lands in a dedicated ``.repo2ree/`` control
directory beneath the logical project root. Inference does not defer to
``ReeIntent.runtime``: that field usually names an *already-built* artifact the
author supplied, which is not where a freshly generated build should write.
"""

from __future__ import annotations

import re
import shlex
from pathlib import PurePosixPath

# Default runtime-artifact names per strategy. Both live beneath the reserved
# control directory under the logical project root. Docker packs an image tar;
# pip packs the virtual environment as a gzipped tarball.
DOCKER_RUNTIME_ARTIFACT_SUFFIX = ".repo2ree/artifacts/runtime.tar"
VENV_RUNTIME_ARTIFACT_SUFFIX = ".repo2ree/artifacts/runtime-venv.tar.gz"


def sh_quote(value: str) -> str:
    """POSIX-shell-quote a value for safe interpolation into a generated script.

    Repository-derived paths and image references are untrusted (a filename may
    contain quotes, ``$``, backticks, or spaces). Every such value is passed
    through this before it lands in the shell body so a crafted name cannot break
    out of its assignment. Constants the renderer itself controls do not need it,
    but quoting them anyway is harmless and keeps the renderers uniform.
    """
    return shlex.quote(value)


def sh_comment(value: str) -> str:
    """Fold an untrusted value onto a single line for a shell comment.

    A newline in a repository-derived value would otherwise end the ``#`` comment
    and inject a live shell line, so collapse all line breaks to spaces.
    """
    return " ".join(value.splitlines()) if value else value


def runtime_artifact_path(project_root: str, suffix: str) -> str:
    """The runtime-artifact path beneath the logical project root."""
    if project_root == ".":
        return suffix
    return str(PurePosixPath(project_root) / suffix)


def runtime_image_ref(ree_name: str) -> str:
    """The Docker image reference a build tags and downstream scripts load.

    ``ree-runtime:<ree-name-slug>`` — readable and stable for a given REE. The
    name is slugified to a valid Docker tag component; an empty or unusable name
    falls back to ``ree``.
    """
    return f"ree-runtime:{_slugify_ree_name(ree_name)}"


# A well-formed Docker tag component: leading alphanumeric/underscore, then up
# to 127 more of the same plus dot and dash.
_DOCKER_TAG = re.compile(r"[a-z0-9_][a-z0-9_.-]{0,127}")


def _slugify_ree_name(name: str) -> str:
    # Docker tag components are `[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}`. Lowercase,
    # fold every other run to a dash, then trim leading/trailing separators so
    # the first character is always alphanumeric or underscore.
    slug = re.sub(r"[^a-z0-9_.-]+", "-", name.strip().lower()).strip("-.")
    slug = slug[:128] or "ree"
    # Postcondition: whatever the input, the result is a valid tag component —
    # this is the one guarantee downstream `docker build --tag` relies on.
    if not _DOCKER_TAG.fullmatch(slug):
        raise AssertionError(f"slugified REE name is not a valid Docker tag component: {slug!r}")
    return slug

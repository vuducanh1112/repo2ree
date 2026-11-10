"""Names a rendered script gives what it builds, derived from the REE's name.

A build writes where its later steps read, on whichever machine runs them: the Docker
image it tags, and the directory its venv is built in. Both follow the REE's name, so
two REEs built side by side on one machine (a store whose workbench runs scripts on its
own host) do not overwrite each other's, and both are the same wherever the REE goes.
"""

from __future__ import annotations

import re

from repo2ree_protocol.inference import DEFAULT_VENV_RESTORE_DIR

# A well-formed Docker tag component: leading alphanumeric/underscore, then up
# to 127 more of the same plus dot and dash.
_DOCKER_TAG = re.compile(r"[a-z0-9_][a-z0-9_.-]{0,127}")


def ree_name_slug(name: str) -> str:
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


def venv_build_dir(ree_name: str) -> str:
    """Where a venv experiment environment is built and restored, for the REE called ``ree_name``.

    Under /tmp, which any machine that reproduces the REE can write: a venv keeps the
    absolute path it was built at, so it is restored to the same one.
    """
    return f"{DEFAULT_VENV_RESTORE_DIR}-{ree_name_slug(ree_name)}"

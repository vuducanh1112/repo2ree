from __future__ import annotations

import re

from repo2ree_protocol.inference import DEFAULT_VENV_RESTORE_DIR

_DOCKER_TAG = re.compile(r"[a-z0-9_][a-z0-9_.-]{0,127}")


def ree_name_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_.-]+", "-", name.strip().lower()).strip("-.")
    slug = slug[:128] or "ree"
    if not _DOCKER_TAG.fullmatch(slug):
        raise AssertionError(f"slugified REE name is not a valid Docker tag component: {slug!r}")
    return slug


def venv_build_dir(ree_name: str) -> str:
    return f"{DEFAULT_VENV_RESTORE_DIR}-{ree_name_slug(ree_name)}"

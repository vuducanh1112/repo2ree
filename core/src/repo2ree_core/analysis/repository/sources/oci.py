"""oci ecosystem parser: ``Dockerfile`` / ``Containerfile`` ``FROM`` references.

A base image is a dependency like any other: the tag is its declared
constraint, a digest pin lands in ``locked_hashes`` (never ``locked_version``).
"""

from __future__ import annotations

import re

from repo2ree_core.analysis.repository.reproducibility_report import is_dockerfile_filename
from repo2ree_core.domain.dependency import Dependency

from .base import SourceParser

_FROM_RE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)(?:\s+[Aa][Ss]\s+(\S+))?\s*$", re.IGNORECASE)


def parse_dockerfile(text: str, path: str) -> list[Dependency]:
    deps: list[Dependency] = []
    stage_aliases: set[str] = set()
    for line in text.splitlines():
        match = _FROM_RE.match(line)
        if not match:
            continue
        ref, alias = match.groups()
        if alias:
            stage_aliases.add(alias.lower())
        if ref.lower() in stage_aliases | {"scratch"} or "$" in ref:
            continue  # multi-stage self-reference, empty base, or build arg
        name, tag, digest = _split_image_ref(ref)
        if not name:
            continue  # degenerate ref like ":tag" or "@digest"
        deps.append(
            Dependency(
                ecosystem="oci",
                name=name,
                declared_constraint=tag,
                declared_in=path,
                locked_hashes=[digest] if digest else [],
            )
        )
    return deps


def _split_image_ref(ref: str) -> tuple[str, str | None, str | None]:
    """``image[:tag][@sha256:...]`` → (name, tag, digest)."""
    digest: str | None = None
    if "@" in ref:
        ref, digest = ref.split("@", 1)
    name, tag = ref, None
    # A colon after the last slash is a tag; earlier ones belong to a registry
    # host:port prefix.
    slash = ref.rfind("/")
    colon = ref.rfind(":")
    if colon > slash:
        name, tag = ref[:colon], ref[colon + 1 :]
    return name, tag or None, digest


PARSERS: tuple[SourceParser, ...] = (
    SourceParser(
        format_id="dockerfile",
        side="declared",
        # docker-compose services reference images differently; not parsed yet.
        matches=lambda name: is_dockerfile_filename(name) and not name.startswith("docker-compose"),
        parse=parse_dockerfile,
    ),
)

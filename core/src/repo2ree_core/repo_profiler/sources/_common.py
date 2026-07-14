"""Helpers shared across ecosystem parser modules."""

from __future__ import annotations

import re
import tomllib

from repo2ree_core.domain.dependency import Dependency, Ecosystem, normalize_package_name

# PEP 508-ish: name, optional extras, then whatever constraint text follows.
_PEP508_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$")


def make_dependency(
    ecosystem: Ecosystem,
    raw_name: str,
    *,
    declared_constraint: str | None,
    declared_in: str,
) -> Dependency:
    name = normalize_package_name(ecosystem, raw_name)
    return Dependency(
        ecosystem=ecosystem,
        name=name,
        name_as_written=raw_name if raw_name != name else None,
        declared_constraint=declared_constraint,
        declared_in=declared_in,
    )


def dependency_from_pep508(spec: str, path: str) -> Dependency | None:
    """A pypi row from a PEP 508 requirement string (markers already stripped)."""
    match = _PEP508_RE.match(spec)
    if not match or not match.group(1):
        return None
    return make_dependency(
        "pypi",
        match.group(1),
        declared_constraint=match.group(2).strip() or None,
        declared_in=path,
    )


def load_toml(text: str) -> dict | None:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None

"""conda ecosystem parser: ``environment.yml`` / ``environment.yaml``.

The ``pip:`` sublist yields pypi rows — conda environments routinely mix the
two ecosystems in one file.
"""

from __future__ import annotations

import re

import yaml

from repo2ree_core.domain.dependency import Dependency

from ._common import dependency_from_pep508, make_dependency
from .base import SourceParser

# conda match specs split at the first comparison operator.
_CONDA_SPEC_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*((?:[=<>!~].*)?)$")


def parse_environment_yml(text: str, path: str) -> list[Dependency]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    deps: list[Dependency] = []
    entries = data.get("dependencies")
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str):
            match = _CONDA_SPEC_RE.match(entry.strip())
            if match and match.group(1).lower() != "python":
                deps.append(
                    make_dependency(
                        "conda",
                        match.group(1),
                        declared_constraint=match.group(2).strip() or None,
                        declared_in=path,
                    )
                )
        elif isinstance(entry, dict):
            pip_entries = entry.get("pip")
            for pip_entry in pip_entries if isinstance(pip_entries, list) else []:
                if isinstance(pip_entry, str) and "://" not in pip_entry:
                    dep = dependency_from_pep508(pip_entry.split(";", 1)[0].strip(), path)
                    if dep is not None:
                        deps.append(dep)
    return deps


PARSERS: tuple[SourceParser, ...] = (
    SourceParser(
        format_id="environment-yml",
        side="declared",
        matches=lambda name: name in {"environment.yml", "environment.yaml"},
        parse=parse_environment_yml,
    ),
)

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import unquote

from repo2ree_ree.dependency import Ecosystem, normalize_package_name

_PURL_ECOSYSTEMS: dict[str, Ecosystem] = {
    "pypi": "pypi",
    "conda": "conda",
    "npm": "npm",
    "deb": "apt",
}


@dataclass(frozen=True)
class ObservedPackage:
    ecosystem: Ecosystem
    name: str
    version: str | None


def parse_cyclonedx(text: str) -> list[ObservedPackage]:
    try:
        data = json.loads(text)
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, dict):
        return []
    components = data.get("components")
    if not isinstance(components, list):
        return []
    packages: list[ObservedPackage] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        package = _from_purl(component.get("purl")) or _from_name(component)
        if package is not None:
            packages.append(package)
    return packages


def _from_purl(purl: object) -> ObservedPackage | None:
    if not isinstance(purl, str) or not purl.startswith("pkg:"):
        return None
    body = purl[len("pkg:") :].split("#", 1)[0].split("?", 1)[0]
    path, _, version = body.partition("@")
    segments = [unquote(segment) for segment in path.split("/") if segment]
    if len(segments) < 2:
        return None
    purl_type = segments[0].lower()
    ecosystem = _PURL_ECOSYSTEMS.get(purl_type, "other")
    name = "/".join(segments[1:]) if ecosystem == "npm" else segments[-1]
    if not name:
        return None
    return ObservedPackage(
        ecosystem=ecosystem,
        name=normalize_package_name(ecosystem, name),
        version=version or None,
    )


def _from_name(component: dict[str, object]) -> ObservedPackage | None:
    name = component.get("name")
    if not isinstance(name, str) or not name:
        return None
    version = component.get("version")
    return ObservedPackage(
        ecosystem="other",
        name=name,
        version=version if isinstance(version, str) and version else None,
    )

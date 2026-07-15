"""CycloneDX adapter: SBOM components -> observed packages.

The observed-side counterpart of the manifest parsers, under the same
obligation: total over arbitrary text — malformed input yields the rows that
did parse, never an exception. Identity comes from the component's purl
(the one key every SBOM format carries), so this adapter is the only place
that knows CycloneDX's shape; everything downstream sees the IR.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import unquote

from repo2ree_core.domain.dependency import Ecosystem, normalize_package_name

# purl type -> our ecosystem. Unlisted types (apk, rpm, golang, ...) map to
# ``other``: they can still be counted, but never joined against manifests.
_PURL_ECOSYSTEMS: dict[str, Ecosystem] = {
    "pypi": "pypi",
    "conda": "conda",
    "npm": "npm",
    "deb": "apt",
}


@dataclass(frozen=True)
class ObservedPackage:
    """One package present in the built runtime."""

    ecosystem: Ecosystem
    name: str  # normalized for its ecosystem — the join key
    version: str | None


def parse_cyclonedx(text: str) -> list[ObservedPackage]:
    """Observed packages out of a CycloneDX JSON document."""
    try:
        data = json.loads(text)
    except Exception:
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
    """``pkg:type/namespace/name@version?qualifiers#subpath`` -> package.

    Only the type/name/version slice matters here; qualifiers and subpath are
    stripped. npm scopes arrive percent-encoded in the namespace segment.
    """
    if not isinstance(purl, str) or not purl.startswith("pkg:"):
        return None
    body = purl[len("pkg:") :].split("#", 1)[0].split("?", 1)[0]
    path, _, version = body.partition("@")
    segments = [unquote(segment) for segment in path.split("/") if segment]
    if len(segments) < 2:
        return None
    purl_type = segments[0].lower()
    ecosystem = _PURL_ECOSYSTEMS.get(purl_type, "other")
    # npm keeps its scope in the name; other namespaces (deb's distro,
    # conda's channel) are packaging metadata, not identity.
    name = "/".join(segments[1:]) if ecosystem == "npm" else segments[-1]
    if not name:
        return None
    return ObservedPackage(
        ecosystem=ecosystem,
        name=normalize_package_name(ecosystem, name),
        version=version or None,
    )


def _from_name(component: dict[str, object]) -> ObservedPackage | None:
    """Fallback for purl-less components: keep them countable as ``other``."""
    name = component.get("name")
    if not isinstance(name, str) or not name:
        return None
    version = component.get("version")
    return ObservedPackage(
        ecosystem="other",
        name=name,
        version=version if isinstance(version, str) and version else None,
    )

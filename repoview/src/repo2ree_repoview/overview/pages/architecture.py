"""Import graphs of the backend and the GUI, and the domain's evidence graph."""

from __future__ import annotations

from repo2ree_repoview.diagrams.architecture import load_config
from repo2ree_repoview.overview.figures import diagram
from repo2ree_repoview.overview.html import section
from repo2ree_repoview.overview.inputs import (
    DIAGRAMS,
    Bundle,
)


def page_architecture(bundle: Bundle) -> str:
    architecture = DIAGRAMS / "architecture"
    # The governed packages, not whatever an older run left behind.
    configured, _, _ = load_config()
    packages = [architecture / f"{package}.svg" for package in configured]
    body = diagram(
        bundle,
        architecture / "workspace.svg",
        "Backend workspace, by package",
        "Cross-package layering, as import-linter enforces it.",
    )
    body += diagram(bundle, architecture / "gui.svg", "GUI, collapsed", "dependency-cruiser over gui/src.")
    body += (
        "<h3>Per package</h3><details><summary>Show the import graph of each backend package</summary>"
        + "".join(diagram(bundle, p, p.stem) for p in packages)
        + diagram(bundle, architecture / "workspace-modules.svg", "Backend workspace, by module")
        + diagram(bundle, architecture / "gui-core.svg", "GUI, functional core expanded")
        + "</details>"
    )
    body += diagram(
        bundle,
        DIAGRAMS / "domain/evidence.svg",
        "Evidence graph",
        "Which receipts and steps depend on which, from core's audit rules.",
    )
    return section(
        "architecture",
        "Architecture",
        "Import graphs of the backend and the GUI, and the domain's evidence graph.",
        body,
    )

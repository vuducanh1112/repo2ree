"""Import graphs of the backend and the GUI, and the domain's evidence graph."""

from __future__ import annotations

from repo2ree_repoview.diagrams.architecture import load_config
from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.figures import DIAGRAMS, diagram
from repo2ree_repoview.overview.html import Page, section


def page_architecture(bundle: Bundle) -> Page:
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
    lede = "Import graphs of the backend and the GUI, and the domain's evidence graph."
    teaser = "Import graphs of the backend and the GUI"
    return Page("architecture", "Architecture", teaser, section("architecture", "Architecture", lede, body))

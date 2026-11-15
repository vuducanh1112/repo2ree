"""API-facing projection of a portable REE and its live file views.

Everything here is read off the REE tree itself, which is why no handle for
that tree appears on the document. A tree is addressed by its
:class:`ReeLayout` — the value that already means "this REE lives here" — and
the name a control plane files it under is that control plane's, owned by
whoever resolved it. Echoing one back as a field would publish an address as
though it were content: inside a workbench the volume is always mounted at
``/ree``, so the only value this layer could supply is identical for every
REE. The API's own ``ReeDocument`` carries the real handle, which the control
plane alone knows.
"""

from __future__ import annotations

from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import ree_steps
from repo2ree_core.operations.read_models.files import list_ree_files, list_workspace_files
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import load_ree
from repo2ree_protocol.catalog import ReeSteps
from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_ree.model import ree_status


def get_ree_document(layout: ReeLayout, *, include_content: bool = True) -> WorkbenchReeDocument:
    directory = ReeDirectory(layout)
    if not directory.manifest_exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    ree = load_ree(layout, directory)
    ree_audit = audit(ree)
    return WorkbenchReeDocument(
        ree=ree,
        status=ree_status(ree),
        audit=ree_audit,
        steps=ree_steps(ree, ree_audit),
        workspace_files=list_workspace_files(layout, include_content=include_content),
        ree_files=list_ree_files(layout, include_content=include_content),
    )


def get_ree_steps(layout: ReeLayout) -> ReeSteps:
    """Where the REE at ``layout`` stands on each authoring step."""
    directory = ReeDirectory(layout)
    if not directory.manifest_exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    ree = load_ree(layout, directory)
    return ree_steps(ree, audit(ree))

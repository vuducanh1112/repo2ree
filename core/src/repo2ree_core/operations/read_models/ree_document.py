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

from repo2ree_authoring.targets import resolve_target
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import ree_steps
from repo2ree_core.domain.ree.transitions import revision_of
from repo2ree_core.operations.handlers.author.file_concurrency import workspace_content_etag
from repo2ree_core.operations.read_models.files import list_ree_files, list_workspace_files
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import load_ree
from repo2ree_core.persistence.run_lock import running_run
from repo2ree_protocol.catalog import ReeSteps
from repo2ree_protocol.command import ScriptTarget, ScriptTargetSelectorArg, TargetKind
from repo2ree_protocol.document import ReeStatusReport, ScriptState, WorkbenchReeDocument
from repo2ree_ree.model import Ree, ree_status


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


def get_ree_status(layout: ReeLayout) -> ReeStatusReport:
    """Where the REE at ``layout`` stands: its steps, its evidence, its scripts, its revision, and the run holding
    it."""
    directory = ReeDirectory(layout)
    if not directory.manifest_exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    ree = load_ree(layout, directory)
    ree_audit = audit(ree)
    return ReeStatusReport(
        name=ree.subject.definition.name,
        status=ree_status(ree),
        revision=str(revision_of(ree)),
        running=running_run(layout),
        steps=ree_steps(ree, ree_audit),
        audit=ree_audit,
        scripts=[
            ScriptState(**target.model_dump(), etag=workspace_content_etag(directory, target.path))
            for target in _script_targets(ree)
        ],
    )


def _script_targets(ree: Ree) -> list[ScriptTarget]:
    fixed: tuple[TargetKind, ...] = (
        "check_working_environment",
        "launch",
        "build_experiment_environment",
        "activate_experiment_environment",
    )
    selectors = [ScriptTargetSelectorArg(kind=kind) for kind in fixed]
    for experiment in ree.subject.definition.experiments:
        selectors += [
            ScriptTargetSelectorArg(kind="experiment_run", experiment_name=experiment.name),
            ScriptTargetSelectorArg(kind="experiment_verify", experiment_name=experiment.name),
        ]
    return [resolve_target(selector) for selector in selectors]

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Final

from repo2ree_core.bundle.export_format import RepositoryExport, ScopeExport
from repo2ree_core.bundle.repository_export import transfer_scope
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError, open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import history_scopes
from repo2ree_core.workspace.integrity import drift_refusal, find_drift


class BundleRefusedError(ValueError):
    pass


SEALED_BY: Final = frozenset({"seal_ree", "sign_ree"})


def _unrecorded(layout: ReeLayout, scope: ReeLayout, history: GitHistory, head: str) -> str:
    within = scope.root.relative_to(layout.root).as_posix()
    named = "the REE" if within == "." else within
    if head == history.initial_snapshot():
        return f"no ree command has worked on {named} since it was initialized, so it has nothing to bundle yet"
    return (
        f"the history of {named} ends in {head}, a commit no ree command made: a bundle carries only what ree recorded"
    )


@contextmanager
def materialized_ree_download(layout: ReeLayout) -> Iterator[Path]:
    if not layout.manifest.is_file():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        root = staging / "export"
        exports: list[ScopeExport] = []
        with ExitStack() as locks:
            histories = [(scope, locks.enter_context(open_history(scope))) for scope in history_scopes(layout)]
            if drift := find_drift(layout):
                raise BundleRefusedError(drift_refusal(layout, drift))
            for scope, history in histories:
                head = history.head_snapshot()
                if head is None:
                    raise HistoryCaptureError("REE has no captured snapshot to export")
                tip = head
                if scope == layout:
                    ree = ReeDirectory(layout).read_ree()
                    if ree.seal:
                        found = None
                        for commit, record in history.completed_operations():
                            if (
                                record["command"]["operation"] not in SEALED_BY
                                or record["operation_status"] != "succeeded"
                            ):
                                continue
                            document = json.loads(history.git("show", f"{commit}:ree.json").stdout)
                            if document.get("seal", {}).get("ree_digest") == str(ree.seal.ree_digest):
                                found = commit
                                break
                        if found is None:
                            raise HistoryCaptureError("Sealed state has no published successful seal operation")
                        head = found
                if not history.records_operation(tip):
                    raise BundleRefusedError(_unrecorded(layout, scope, history, tip))
                relative = scope.root.relative_to(layout.root).as_posix()
                exports.append(
                    transfer_scope(
                        history,
                        root / "ree" / relative,
                        head=head,
                        scope=relative,
                        bundle=staging / f"scope-{len(exports)}.bundle",
                    )
                )
        metadata = RepositoryExport(scopes=tuple(exports))
        (root / "export.json").write_text(metadata.model_dump_json(indent=2))
        destination = staging / "download.zip"
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for directory, _dirs, files in root.walk():
                for name in sorted(files):
                    path = directory / name
                    relative = path.relative_to(root).as_posix()
                    if path.is_symlink():
                        info = zipfile.ZipInfo(relative)
                        info.create_system = 3
                        info.external_attr = 0o120777 << 16
                        archive.writestr(info, os.fsencode(path.readlink()))
                    else:
                        archive.write(path, relative)
        yield destination

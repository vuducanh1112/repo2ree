"""Download envelope: an unchanged portable bundle plus local Git histories."""

from __future__ import annotations

import json
import stat
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from repo2ree_core.bundle.seal import materialized_ree_archive
from repo2ree_core.persistence.history import SELECTION_VERSION, open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import history_scopes


@contextmanager
def materialized_ree_download(layout: ReeLayout) -> Iterator[Path]:
    """Stage a consistent export under capture locks, then release before streaming."""
    if not layout.manifest.is_file():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    with tempfile.TemporaryDirectory() as temporary:
        destination = Path(temporary) / "download.zip"
        with ExitStack() as locks:
            author = locks.enter_context(open_history(layout))
            author.capture_initial(existing=True)
            scopes = history_scopes(layout)
            heads: dict[str, str] = {}
            histories = [author]
            histories.extend(locks.enter_context(open_history(scope)) for scope in scopes[1:] if scope.git_dir.is_dir())
            with materialized_ree_archive(layout) as portable, zipfile.ZipFile(destination, "w") as archive:
                archive.write(portable, "ree.zip")
                for history in histories:
                    scope = history.layout
                    if head := history.head_snapshot():
                        heads[scope.root.relative_to(layout.root).as_posix()] = head
                    for directory, _directories, files in scope.git_dir.walk(on_error=_walk_error):
                        for name in sorted(files):
                            path = directory / name
                            # Copy bytes only; do not follow links into external storage.
                            if not stat.S_ISREG(path.lstat().st_mode):
                                raise RuntimeError(f"Cannot export non-regular Git storage: {path.name}")
                            archive.write(path, f"ree/{path.relative_to(layout.root).as_posix()}")
                archive.writestr(
                    "export.json",
                    json.dumps(
                        {
                            "schema_version": 1,
                            "selection_version": SELECTION_VERSION,
                            "portable_bundle": "ree.zip",
                            "history_heads": heads,
                            "history_scope": "captured state only; pending attempts may be unresolved",
                        },
                        indent=2,
                    ),
                )
        yield destination


def _walk_error(error: OSError) -> None:
    raise error

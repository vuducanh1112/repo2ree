"""Pure helpers for the downloadable REE bundle ZIP.

The bundle mirrors the on-disk REE layout under a ``ree/`` prefix, plus two
top-level files that make the download self-reproducing without repo2ree:

    run.sh                one-click reproducer (see ``ree_scripts.reproducer``)
    REPRODUCING.md        human instructions for the reproducer
    ree/ree.json          the REE document, the same file the workbench keeps
    ree/snapshot.tar.gz   frozen source archive (when available)
    ree/overlay/...       user recipe files (empty dir entry if none)
    ree/artifacts/...     build outputs (runtime, sbom, ...)
    ree/results/<name>/   author result baselines for sealed experiments (opt-in)
    ree/workspace/        empty placeholder — materialized by run.sh on extract

``upstream/`` is intentionally omitted: its contents are already in
``snapshot.tar.gz``. The paths above are spelled once, in
``persistence.layout``'s bundle section, where they sit beside the on-disk
dirnames they are derived from — the sketch here is a reader's aid, not a
second source of truth.

This module is the functional core for the bundle: the ZIP writer and pure
mapping helpers. All filesystem I/O lives in the shell
(``repo2ree_core.bundle.seal`` and ``repo2ree_core.bundle.restore``).
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable

# ================================================
# Constants
# ================================================


_EPOCH_DATE_TIME = (1980, 1, 1, 0, 0, 0)


# ================================================
# Helpers
# ================================================


def build_zip_bytes(entries: Iterable[tuple[str, bytes]]) -> bytes:
    """Pack ``entries`` into a deflate-compressed ZIP and return the bytes.

    ``entries`` is a sequence of ``(archive_path, content_bytes)`` pairs. An
    entry whose ``archive_path`` ends with ``/`` is written as an empty
    directory. Entries receive a fixed epoch timestamp so the output is
    byte-identical for identical inputs (enabling content-addressed seal hashes).
    Shell scripts (``*.sh``) are marked executable so the materialized workspace
    and the bundled ``run.sh`` are directly runnable after extraction. Pure
    given its inputs: no filesystem access.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_path, content in entries:
            info = zipfile.ZipInfo(filename=archive_path, date_time=_EPOCH_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = _unix_mode_attr(archive_path)
            archive.writestr(info, content)
    return buffer.getvalue()


def _unix_mode_attr(archive_path: str) -> int:
    """Unix permission bits for a ZIP entry, as the high 16 bits of external_attr."""
    if archive_path.endswith("/"):
        mode = 0o40755  # directory
    elif archive_path.endswith(".sh"):
        mode = 0o100755  # executable script
    else:
        mode = 0o100644  # regular file
    return mode << 16

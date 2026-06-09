"""Fetch source bytes from a URL or local path into a destination file.

Shell module: performs network and filesystem I/O. Independent of the REE
concept so any flow that needs to materialize a remote or local file into
a known path can reuse it.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


def download_or_copy(origin_url: str, destination: Path) -> Path:
    """Place the bytes referenced by ``origin_url`` at ``destination``.

    Supports ``http`` and ``https`` URLs (streamed download) and local
    filesystem paths (copied with metadata preserved). Raises
    :class:`FileNotFoundError` if the source is neither reachable nor a
    local path that exists.
    """
    parsed = urlparse(origin_url)
    if parsed.scheme in {"http", "https"}:
        # urlopen is stdlib — requests is not available in the workbench image.
        # Scheme is validated on the line above, so only http/https reach here.
        with urlopen(origin_url) as response, destination.open("wb") as target:  # noqa: S310
            shutil.copyfileobj(response, target)
        return destination

    local_path = Path(origin_url)
    if local_path.exists():
        shutil.copy2(local_path, destination)
        return destination

    raise FileNotFoundError(f"Source not found: {origin_url}")

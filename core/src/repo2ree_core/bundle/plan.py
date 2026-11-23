from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable

_EPOCH_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def deterministic_zip_info(archive_path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=archive_path, date_time=_EPOCH_DATE_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = _unix_mode_attr(archive_path)
    return info


def build_zip_bytes(entries: Iterable[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_path, content in entries:
            archive.writestr(deterministic_zip_info(archive_path), content)
    return buffer.getvalue()


def _unix_mode_attr(archive_path: str) -> int:
    if archive_path.endswith("/"):
        mode = 0o40755
    elif archive_path.endswith(".sh"):
        mode = 0o100755
    else:
        mode = 0o100644
    return mode << 16

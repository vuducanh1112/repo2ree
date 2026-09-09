from __future__ import annotations

import pytest

from repo2ree_core.bundle.seal import BundleProgress
from repo2ree_core.operations.handlers.author.seal_ree import _format_bytes, _ProgressLogger


@pytest.mark.parametrize(
    ("value", "rendered"),
    [
        (999, "999 B"),
        (1024, "1.0 KiB"),
        (5 * 1024 * 1024, "5.0 MiB"),
        (3 * 1024 * 1024 * 1024, "3.0 GiB"),
    ],
)
def test_format_bytes_uses_human_readable_binary_units(value: int, rendered: str) -> None:
    assert _format_bytes(value) == rendered


def test_seal_progress_log_uses_human_readable_sizes() -> None:
    messages: list[str] = []
    report = _ProgressLogger(lambda _stream, _level, message: messages.append(message))

    report(
        BundleProgress(
            phase="writing",
            bytes_processed=5 * 1024 * 1024,
            bytes_total=20 * 1024 * 1024,
            archive_bytes=2 * 1024 * 1024,
            entries_processed=1,
            entries_total=4,
        )
    )

    assert messages == ["Writing sealed bundle: 5.0 MiB / 20.0 MiB (25%), 1/4 entries"]

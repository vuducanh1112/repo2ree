"""Pure request-plumbing helpers shared across the routers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from repo2ree_api.api_utils import (
    WORKSPACE_CONTROL_PREFIXES,
    keyset_paginate,
    require_non_empty_path,
    resolve_relative_path,
)
from repo2ree_core.run_script import stream_output

# ================================================
# keyset_paginate
# ================================================


# Sorted descending by (created_at, id), the order the routes hand in.
ITEMS = [
    {"created_at": "t5", "id": "e"},
    {"created_at": "t4", "id": "d"},
    {"created_at": "t3", "id": "c"},
    {"created_at": "t2", "id": "b"},
    {"created_at": "t1", "id": "a"},
]


def _key(item: dict[str, str]) -> tuple[str, str]:
    return item["created_at"], item["id"]


def test_keyset_no_cursor_no_limit_returns_everything():
    page, next_cursor, has_more = keyset_paginate(ITEMS, cursor=None, limit=None, key=_key)
    assert page == ITEMS
    assert next_cursor is None
    assert has_more is False


def test_keyset_limit_slices_and_encodes_last_key_as_cursor():
    page, next_cursor, has_more = keyset_paginate(ITEMS, cursor=None, limit=2, key=_key)
    assert page == ITEMS[:2]
    assert next_cursor == "t4~d"
    assert has_more is True


def test_keyset_cursor_continues_strictly_after_the_cursor_key():
    page, next_cursor, has_more = keyset_paginate(ITEMS, cursor="t4~d", limit=2, key=_key)
    assert page == ITEMS[2:4]
    assert next_cursor == "t2~b"
    assert has_more is True


def test_keyset_last_page_has_no_next_cursor():
    page, next_cursor, has_more = keyset_paginate(ITEMS, cursor="t2~b", limit=10, key=_key)
    assert page == ITEMS[4:]
    assert next_cursor is None
    assert has_more is False


def test_keyset_items_created_between_pages_do_not_shift_the_boundary():
    # A new item at the head (newest) must not push earlier items into the
    # next page — the failure mode of offset cursors.
    grown = [{"created_at": "t6", "id": "f"}, *ITEMS]
    page, _, _ = keyset_paginate(grown, cursor="t4~d", limit=2, key=_key)
    assert page == ITEMS[2:4]


def test_keyset_malformed_cursor_is_a_400_invalid_cursor():
    with pytest.raises(HTTPException) as excinfo:
        keyset_paginate(ITEMS, cursor="no-separator", limit=2, key=_key)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail["code"] == "invalid_cursor"


# ================================================
# require_non_empty_path
# ================================================


def test_require_non_empty_path_strips_and_returns():
    assert require_non_empty_path("  src/app.py ", "path") == "src/app.py"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_require_non_empty_path_rejects_blank(value: str | None):
    with pytest.raises(HTTPException) as excinfo:
        require_non_empty_path(value, "path")
    assert excinfo.value.status_code == 400
    assert "path is required" in str(excinfo.value.detail)


# ================================================
# resolve_relative_path
# ================================================


def test_resolve_relative_path_stays_inside_root(tmp_path: Path):
    resolved = resolve_relative_path(tmp_path, "sub/file.txt", invalid_detail="invalid path")
    assert resolved == tmp_path / "sub" / "file.txt"


@pytest.mark.parametrize("escape", ["../outside.txt", "sub/../../outside.txt"])
def test_resolve_relative_path_rejects_traversal(tmp_path: Path, escape: str):
    with pytest.raises(HTTPException) as excinfo:
        resolve_relative_path(tmp_path, escape, invalid_detail="invalid path")
    assert excinfo.value.status_code == 400


def test_resolve_relative_path_blocks_workspace_control_files(tmp_path: Path):
    with pytest.raises(HTTPException):
        resolve_relative_path(
            tmp_path,
            ".workspace.json",
            invalid_detail="invalid path",
            blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
        )
    # blocking is by basename prefix, so nested control files are caught too
    with pytest.raises(HTTPException):
        resolve_relative_path(
            tmp_path,
            "sub/.upload.tok.bin",
            invalid_detail="invalid path",
            blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
        )


# ================================================
# stream_output
# ================================================


def test_stream_output_maps_streams_and_skips_blanks():
    result = subprocess.CompletedProcess(
        args=["tool"], returncode=0, stdout="line one\n\n  \nline two\n", stderr="warn line\n"
    )
    captured: list[tuple[str, str, str]] = []
    stream_output(lambda s, lvl, msg: captured.append((s, lvl, msg)), result)
    assert captured == [
        ("stdout", "info", "line one"),
        ("stdout", "info", "line two"),
        ("stderr", "warn", "warn line"),
    ]

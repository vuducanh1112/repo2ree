"""Pure request-plumbing helpers shared across the routers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from repo2ree_api.api_utils import (
    WORKSPACE_CONTROL_PREFIXES,
    append_completed_process_output,
    paginate,
    require_non_empty_path,
    resolve_relative_path,
)

# ================================================
# paginate
# ================================================


ITEMS = [{"i": i} for i in range(5)]


def test_paginate_no_cursor_no_limit_returns_everything():
    page, next_cursor, has_more = paginate(ITEMS, cursor=None, limit=None)
    assert page == ITEMS
    assert next_cursor is None
    assert has_more is False


def test_paginate_limit_slices_and_reports_more():
    page, next_cursor, has_more = paginate(ITEMS, cursor=None, limit=2)
    assert page == ITEMS[:2]
    assert next_cursor == "2"
    assert has_more is True


def test_paginate_cursor_continues_where_the_last_page_ended():
    page, next_cursor, has_more = paginate(ITEMS, cursor="2", limit=2)
    assert page == ITEMS[2:4]
    assert next_cursor == "4"
    assert has_more is True


def test_paginate_last_page_has_no_next_cursor():
    page, next_cursor, has_more = paginate(ITEMS, cursor="4", limit=10)
    assert page == ITEMS[4:]
    assert next_cursor is None
    assert has_more is False


def test_paginate_garbage_or_negative_cursor_starts_at_zero():
    assert paginate(ITEMS, cursor="garbage", limit=1)[0] == ITEMS[:1]
    assert paginate(ITEMS, cursor="-3", limit=1)[0] == ITEMS[:1]


def test_paginate_negative_limit_is_ignored():
    page, _, has_more = paginate(ITEMS, cursor=None, limit=-1)
    assert page == ITEMS
    assert has_more is False


def test_paginate_zero_limit_returns_empty_page():
    page, next_cursor, has_more = paginate(ITEMS, cursor=None, limit=0)
    assert page == []
    assert next_cursor == "0"
    assert has_more is True


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
# append_completed_process_output
# ================================================


def test_append_completed_process_output_maps_streams_and_skips_blanks():
    result = subprocess.CompletedProcess(
        args=["tool"], returncode=0, stdout="line one\n\n  \nline two\n", stderr="warn line\n"
    )
    captured: list[tuple[str, str, str]] = []
    append_completed_process_output(result, lambda s, lvl, msg: captured.append((s, lvl, msg)))
    assert captured == [
        ("stdout", "info", "line one"),
        ("stdout", "info", "line two"),
        ("stderr", "warn", "warn line"),
    ]

"""Tool resolution: injected REPO2REE_TOOL_* paths win, PATH is the fallback."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from repo2ree_core.execution.tools import find_tool, resolve_tool, tool_env_var


def test_env_var_name_normalises_dashes() -> None:
    assert tool_env_var("my-tool") == "REPO2REE_TOOL_MY_TOOL"


def test_resolve_prefers_advertised_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO2REE_TOOL_SYFT", "/nix/store/x/bin/syft")
    assert resolve_tool("syft") == "/nix/store/x/bin/syft"


def test_resolve_falls_back_to_bare_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPO2REE_TOOL_SYFT", raising=False)
    assert resolve_tool("syft") == "syft"


def test_find_tool_verifies_advertised_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tool = tmp_path / "syft"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("REPO2REE_TOOL_SYFT", str(tool))
    assert find_tool("syft") == str(tool)

    # An advertised path that doesn't exist is unavailable, not a PATH retry:
    # the agent said where the tool lives, and it lied.
    monkeypatch.setenv("REPO2REE_TOOL_SYFT", str(tmp_path / "missing"))
    assert find_tool("syft") is None


def test_find_tool_uses_path_when_not_advertised(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tool = tmp_path / "sometool"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    monkeypatch.delenv("REPO2REE_TOOL_SOMETOOL", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    assert find_tool("sometool") == str(tool)

"""A CLI test's session video is rendered once per recording and renderer, beside its run, and goes with its test."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from repo2ree_testbed.runs import session_videos
from repo2ree_testbed.runs.session_videos import Session, drop_gone, render, sessions


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """agg and ffmpeg, as each writes its output: the last argument."""
    ran: list[str] = []

    def run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        ran.append(command[0])
        Path(command[-1]).write_bytes(f"{command[0]} output".encode())
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(session_videos, "renderer", lambda: "agg 1 / ffmpeg 9")
    return ran


def recorded(run: Path, test: str, content: str = "cast") -> Path:
    cast = run / "tests" / test / "artifacts" / "cli-session.cast"
    cast.parent.mkdir(parents=True)
    cast.write_text(content)
    return cast


def test_a_video_renders_once_and_again_only_when_its_recording_changes(tmp_path: Path, tools: list[str]) -> None:
    run = tmp_path / "showcase-cli-1"
    cast = recorded(run, "test-a")
    [session] = sessions(run, tmp_path / "sessions")
    assert session.video == tmp_path / "sessions/showcase-cli-1/test-a.mp4"

    assert render(session) is True
    assert render(session) is False, "its key is the one there"
    cast.write_text("another cast")
    assert render(session) is True

    assert tools == ["agg", "ffmpeg", "agg", "ffmpeg"]
    assert session.video.read_bytes() == b"ffmpeg output"


def test_a_video_renders_again_when_how_it_is_rendered_changes(
    tmp_path: Path, tools: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    run = tmp_path / "showcase-cli-1"
    recorded(run, "test-a")
    [session] = sessions(run, tmp_path / "sessions")
    render(session)

    monkeypatch.setattr(session_videos, "renderer", lambda: "agg 2 / ffmpeg 9")

    assert render(session) is True


def test_videos_of_tests_a_run_no_longer_has_go(tmp_path: Path, tools: list[str]) -> None:
    run, videos = tmp_path / "showcase-cli-1", tmp_path / "sessions"
    recorded(run, "test-a")
    for session in sessions(run, videos):
        render(session)
    stale = Session(cast=run / "gone.cast", video=videos / "showcase-cli-1/test-gone.mp4")
    stale.video.write_bytes(b"old")
    stale.key_file.write_text("old")

    drop_gone({"showcase-cli-1": sessions(run, videos)}, videos)

    assert sorted(path.name for path in (videos / "showcase-cli-1").iterdir()) == ["test-a.key", "test-a.mp4"]

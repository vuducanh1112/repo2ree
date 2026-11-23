from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from repo2ree_testbed.cli_cast import Header, Printed, append_command


def recorded(path: Path) -> tuple[Header, list[list[Any]]]:
    header, *events = path.read_text(encoding="utf-8").splitlines()
    return Header.model_validate_json(header), [json.loads(event) for event in events]


def test_a_command_is_its_prompt_then_its_output_when_it_arrived(tmp_path: Path) -> None:
    cast = tmp_path / "test-x" / "artifacts" / "cli-session.cast"
    append_command(
        cast,
        ("ree", "-C", "/w/a b", "--json", "status"),
        stdin_bytes=0,
        started=1000.25,
        finished=1003.0,
        printed=(Printed(1001.0, "stderr", b"building\n"), Printed(1002.5, "stdout", b'{"status":"succeeded"}\n')),
    )
    header, events = recorded(cast)
    assert (header.version, header.timestamp, header.title) == (2, 1000, "test-x")
    assert events == [
        [0.25, "o", "\x1b[1m$ ree -C '/w/a b' --json status\x1b[0m\r\n"],
        [1.0, "o", "building\r\n"],
        [2.5, "o", '{"status":"succeeded"}\r\n'],
    ]


def test_a_prompt_names_the_directory_the_command_ran_in(tmp_path: Path) -> None:
    cast = tmp_path / "cli-session.cast"
    append_command(
        cast, ("ree", "status"), where="demo-1a2b", stdin_bytes=0, started=1000.0, finished=1000.5, printed=()
    )
    _, events = recorded(cast)
    assert events[0][2] == "\x1b[36mdemo-1a2b\x1b[0m \x1b[1m$ ree status\x1b[0m\r\n"


def test_later_commands_keep_the_recordings_start(tmp_path: Path) -> None:
    cast = tmp_path / "cli-session.cast"
    append_command(cast, ("ree", "status"), stdin_bytes=0, started=1000.0, finished=1001.0, printed=())
    append_command(
        cast,
        ("ree", "write-script", "run.sh"),
        stdin_bytes=12,
        started=1010.0,
        finished=1011.0,
        printed=(Printed(1010.5, "stdout", b"ok"),),
    )
    header, events = recorded(cast)
    assert header.timestamp == 1000
    assert events[1] == [10.0, "o", "\x1b[1m$ ree write-script run.sh  # 12 bytes on stdin\x1b[0m\r\n"]
    assert events[2:] == [[10.5, "o", "ok"], [11.0, "o", "\r\n"]]


def test_a_character_split_across_chunks_is_one_character(tmp_path: Path) -> None:
    cast = tmp_path / "cli-session.cast"
    arrow = "→".encode()
    append_command(
        cast,
        ("ree", "status"),
        stdin_bytes=0,
        started=1000.0,
        finished=1002.0,
        printed=(Printed(1000.5, "stderr", arrow[:1]), Printed(1001.0, "stderr", arrow[1:] + b"\n")),
    )
    _, events = recorded(cast)
    assert [event[2] for event in events[1:]] == ["→\r\n"]


def test_time_never_runs_backwards(tmp_path: Path) -> None:
    cast = tmp_path / "cli-session.cast"
    append_command(
        cast,
        ("ree", "status"),
        stdin_bytes=0,
        started=1000.0,
        finished=1002.0,
        printed=(Printed(1001.0, "stdout", b"a\n"), Printed(1000.9, "stderr", b"b\n")),
    )
    _, events = recorded(cast)
    times = [event[0] for event in events]
    assert times == sorted(times)


def test_output_that_is_not_text_is_noted_by_its_size(tmp_path: Path) -> None:
    cast = tmp_path / "cli-session.cast"
    append_command(
        cast,
        ("ree", "bundle"),
        stdin_bytes=0,
        started=1000.0,
        finished=1003.0,
        printed=(
            Printed(1001.0, "stdout", b"PK\x03\x04\xff"),
            Printed(1001.5, "stderr", b"bundled\n"),
            Printed(1002.0, "stdout", b"\x00\xfe"),
        ),
    )
    _, events = recorded(cast)
    assert events[1:] == [
        [1.5, "o", "bundled\r\n"],
        [2.0, "o", "\x1b[2m[7 bytes on stdout, not text]\x1b[0m\r\n"],
    ]

from pathlib import Path

from repo2ree_core.container.run_script import build_exec_command


def test_exec_command_without_label_does_not_echo_script():
    payload = build_exec_command(
        Path("/workspace/sub/run.sh"), "sub/run.sh", echo_label=None
    )

    assert payload == "set -e; cd /workspace/sub; sh /workspace/sub/run.sh"


def test_exec_command_can_override_working_dir():
    payload = build_exec_command(
        Path("/workspace/.workspace/run.sh"),
        ".workspace/run.sh",
        echo_label=None,
        working_dir=Path("/workspace"),
    )

    assert payload == "set -e; cd /workspace; sh /workspace/.workspace/run.sh"


def test_exec_command_with_label_echoes_and_cats_script():
    payload = build_exec_command(
        Path("/workspace/sub/run.sh"), "sub/run.sh", echo_label="build_runtime_script"
    )

    segments = payload.split("; ")
    assert segments[0] == "set -e"
    assert segments[1] == "cd /workspace/sub"
    assert "--- build_runtime_script (sub/run.sh) ---" in segments[2]
    assert segments[3] == "cat /workspace/sub/run.sh"
    assert "--- end build_runtime_script ---" in segments[4]
    assert segments[-1] == "sh /workspace/sub/run.sh"


def test_exec_command_quotes_paths_with_spaces():
    payload = build_exec_command(
        Path("/workspace/a b/run.sh"), "a b/run.sh", echo_label=None
    )

    assert "cd '/workspace/a b'" in payload
    assert "sh '/workspace/a b/run.sh'" in payload

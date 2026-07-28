import os
import time
from pathlib import Path

import repo2ree_core.execution.process as run_script
from repo2ree_core.execution.process import CancelCheck, run_streaming_process


def test_run_streaming_process_logs_and_captures_stdout_stderr():
    logged: list[tuple[str, str, str]] = []

    result = run_streaming_process(
        ["sh", "-c", "printf 'out\\n'; printf 'err\\n' >&2"],
        log=lambda stream, level, msg: logged.append((stream, level, msg)),
    )

    assert result.returncode == 0
    assert result.stdout == "out\n"
    assert result.stderr == "err\n"
    assert ("stdout", "info", "out") in logged
    assert ("stderr", "warn", "err") in logged


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_pid_gone(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return False


def _cancel_once_pid_recorded(pid_file: Path) -> CancelCheck:
    """is_canceled that flips true as soon as the child has recorded its pid."""

    def is_canceled() -> bool:
        return pid_file.is_file() and pid_file.read_text().strip() != ""

    return is_canceled


def test_cancel_kills_whole_process_tree(tmp_path):
    """A cooperative child (and its parent shell) die when the run is canceled."""
    pid_file = tmp_path / "child.pid"
    # Background a child that records its pid, then the shell waits on it. The
    # child is a descendant, not the shell itself — the point is that signalling
    # only the shell leader would leave it orphaned.
    script = f"sleep 30 & echo $! > {pid_file}; wait"

    result = run_streaming_process(
        ["sh", "-c", script],
        log=lambda *_: None,
        is_canceled=_cancel_once_pid_recorded(pid_file),
    )

    assert result.canceled is True
    child_pid = int(pid_file.read_text().strip())
    assert _wait_pid_gone(child_pid), "canceled child process survived"


def test_cancel_escalates_to_sigkill_when_sigterm_ignored(tmp_path, monkeypatch):
    """A process that traps SIGTERM is still killed after the grace deadline."""
    # Keep the test fast: shrink the SIGTERM->SIGKILL window the ladder waits.
    monkeypatch.setattr(run_script, "CANCEL_GRACE_SECONDS", 0.5)
    pid_file = tmp_path / "child.pid"
    # Run a script (avoids nested-shell quoting) whose process ignores TERM and
    # loops forever, so only SIGKILL to the group can stop it. It records its own
    # pid ($$) so we can watch that exact process.
    stubborn = tmp_path / "stubborn.sh"
    stubborn.write_text(f"trap '' TERM\necho $$ > {pid_file}\nwhile true; do sleep 0.2; done\n")

    logged: list[tuple[str, str, str]] = []
    result = run_streaming_process(
        ["sh", str(stubborn)],
        log=lambda stream, level, msg: logged.append((stream, level, msg)),
        is_canceled=_cancel_once_pid_recorded(pid_file),
    )

    assert result.canceled is True
    child_pid = int(pid_file.read_text().strip())
    assert _wait_pid_gone(child_pid), "SIGTERM-ignoring process survived escalation"
    assert any("SIGKILL" in msg for _, _, msg in logged), "escalation was not logged"


def test_truncated_output_is_reported_rather_than_returned_quietly(tmp_path, monkeypatch):
    """A grandchild holding the pipe open past the drain window is announced.

    Everything downstream — run log, receipt, span failure tails — is built from
    the captured buffers, so a short read that says nothing reads as "the script
    printed nothing more", which is the one thing it does not mean.
    """
    # Keep the test fast: shrink the window the readers get to drain.
    monkeypatch.setattr(run_script, "READER_DRAIN_SECONDS", 0.2)
    # The parent exits immediately; the backgrounded subshell inherits its
    # stdout and holds the pipe open well past the drain deadline.
    holder = tmp_path / "holder.sh"
    holder.write_text("printf 'first\\n'\n(sleep 2; printf 'late\\n') &\n")

    logged: list[tuple[str, str, str]] = []
    result = run_streaming_process(
        ["sh", str(holder)],
        log=lambda stream, level, msg: logged.append((stream, level, msg)),
    )

    assert result.returncode == 0
    # What was read before the deadline is still returned.
    assert "first" in result.stdout
    # ...and the fact that more may be missing is said out loud.
    assert any(stream == "system" and level == "warn" and "truncated" in msg for stream, level, msg in logged), (
        f"truncation was not reported: {logged}"
    )


def test_a_process_that_closes_its_pipes_reports_no_truncation(tmp_path):
    logged: list[tuple[str, str, str]] = []

    run_streaming_process(
        ["sh", "-c", "printf 'done\\n'"],
        log=lambda stream, level, msg: logged.append((stream, level, msg)),
    )

    assert not any("truncated" in msg for _, _, msg in logged)

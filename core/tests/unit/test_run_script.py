from repo2ree_core.run_script import run_streaming_process


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

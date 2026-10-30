import json
from pathlib import Path

from repo2ree_testbed.runs.failed_command import FailedCommand, last_failed_command

# The tail the VM's e2e-gui run recorded, trimmed: a build whose RUN step could not resolve names.
PIP_TAIL = """\
ror('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x7f>: Failed to establish a new connection: \
[Errno -3] Temporary failure in name resolution')': /simple/pandas/
89.12 WARNING: Retrying (Retry(total=0)) after connection broken by 'NewConnectionError(...)': /simple/pandas/
105.1 ERROR: No matching distribution found for pandas==2.2.1
------
  11 | >>> RUN pip install --no-cache-dir -r requirements.txt
ERROR: failed to build: failed to solve: process "/bin/sh -c pip install" did not complete successfully: exit code: 1
"""


def span(end: str, *, status: str = "ERROR", canceled: bool = False, argv: str = "sh build.sh", tail: str = "") -> str:
    attributes = {
        "repo2ree.exec.argv": argv,
        "repo2ree.exit_code": 1,
        "repo2ree.canceled": canceled,
        "repo2ree.exec.stderr_tail": tail,
    }
    return json.dumps(
        {"name": "process.exec", "end_time": end, "status": {"status_code": status}, "attributes": attributes}
    )


def test_the_summary_keeps_the_first_failure_line_and_the_last() -> None:
    summary = FailedCommand("sh ree-scripts/build_script.sh", 1, PIP_TAIL).summary()

    assert summary.startswith("`sh ree-scripts/build_script.sh` exited 1: ")
    assert "Temporary failure in name resolution" in summary
    assert summary.endswith("did not complete successfully: exit code: 1")
    assert "No matching distribution" not in summary


def test_a_tail_without_failure_lines_names_only_the_command() -> None:
    assert FailedCommand("make", 2, "building\nstill building\n").summary() == "`make` exited 2"


def test_the_latest_failed_uncanceled_command_across_span_files_is_the_one(tmp_path: Path) -> None:
    (tmp_path / "api.ndjson").write_text(
        "\n".join(
            [
                span("2026-10-29T22:01:00Z", argv="early failure"),
                span("2026-10-29T22:08:19Z", argv="sh build.sh", tail=PIP_TAIL),
                span("2026-10-29T22:09:00Z", argv="canceled later", canceled=True),
                span("2026-10-29T22:10:00Z", argv="succeeded later", status="UNSET"),
                "not json",
            ]
        )
    )
    (tmp_path / "location-1.ndjson").write_text(json.dumps({"name": "docker.run", "end_time": "2026-10-29T23:00:00Z"}))

    failed = last_failed_command(tmp_path)

    assert failed is not None
    assert failed.argv == "sh build.sh"
    assert failed.stderr_tail == PIP_TAIL


def test_no_telemetry_means_no_failed_command(tmp_path: Path) -> None:
    assert last_failed_command(tmp_path / "missing") is None

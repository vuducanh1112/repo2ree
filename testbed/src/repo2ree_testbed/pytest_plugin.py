"""Shared recording lifecycle for every pytest suite."""

from __future__ import annotations

import json
import os
import warnings
from collections import Counter
from collections.abc import Generator, Iterator
from pathlib import Path

import pytest

from repo2ree_testbed.artifacts import artifact_domain, case_key, domain_dir, execution_id, write_provenance
from repo2ree_testbed.recording import TestRecorder

_OUTCOME = pytest.StashKey[str]()
_RECORDER = pytest.StashKey[TestRecorder]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if report.failed or report.skipped or report.when == "call":
        item.stash[_OUTCOME] = report.outcome
    if report.when == "teardown" and (recorder := item.stash.get(_RECORDER, None)) is not None:
        recorder.finish(item.stash.get(_OUTCOME, report.outcome))
    return report


@pytest.fixture(autouse=True)
def test_recording(request: pytest.FixtureRequest) -> Iterator[TestRecorder]:
    recorder = TestRecorder(request.node.nodeid)
    request.node.stash[_RECORDER] = recorder
    trace = Path(os.environ["TRACE_FILE"]) if os.environ.get("TRACE_FILE") else None
    start = trace.stat().st_size if trace and trace.exists() else 0
    yield recorder
    temporary = request.node.funcargs.get("tmp_path")
    if isinstance(temporary, Path) and temporary.exists():
        recorder.discover(temporary)
    recorder.directory.mkdir(parents=True, exist_ok=True)
    if trace and trace.exists():
        with trace.open("rb") as source:
            source.seek(start)
            chunk = source.read()
        if chunk:
            (recorder.directory / "traces.ndjson").write_bytes(chunk)
    recorder.finish(request.node.stash.get(_OUTCOME, "completed"))
    errors = [item for item in recorder.repositories if item["status"] == "error"]
    if errors:
        warnings.warn(pytest.PytestWarning(f"REE recording errors: {errors}"), stacklevel=1)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    suite = " ".join(str(arg) for arg in session.config.args)
    counts = Counter(artifact_domain(item.nodeid) for item in session.items)
    if not counts:
        counts.update({artifact_domain(str(arg)): 0 for arg in session.config.args})
    for domain, tests in sorted(counts.items()):
        directory = domain_dir(domain) / "sessions"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{case_key(suite)}.json").write_text(
            json.dumps(
                {
                    "suite": suite,
                    "execution_id": execution_id(),
                    "exitstatus": exitstatus,  # Status of the whole pytest session, including mixed suites.
                    "tests": tests,
                    "artifact_domain": domain,
                }
            )
            + "\n"
        )
    if coverage_file := os.environ.get("COVERAGE_FILE"):
        write_provenance(Path(coverage_file).parent)

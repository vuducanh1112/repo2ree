"""A recording collected through the control plane lists every source with its origin, cut, and problems."""

from __future__ import annotations

import hashlib
import io
import json
import threading
import zipfile
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from repo2ree_collect import (
    ControlPlane,
    archive,
    collect_control_plane,
    download_archive,
    kept_archives,
    spans,
    start,
    stopped_owners,
)
from repo2ree_collect.cli import main
from repo2ree_conformance import load_recording
from repo2ree_recording import read_recording


def record(seq: int, **fields: object) -> bytes:
    return json.dumps({"v": 1, "seq": seq, **fields}, separators=(",", ":"), sort_keys=True).encode() + b"\n"


JOURNAL = record(
    1, kind="journal.opened", process="api", epoch=1, hosts=["api", "supervisor"], vocabulary="sha256:x"
) + record(
    2,
    kind="transition",
    owner="api",
    subject="Run",
    key="build-1",
    partition="ree-1",
    to="queued",
    facts={"operation": "build"},
)


def bundle(*members: tuple[str, str]) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, content in members:
            archive.writestr(name, content)
    return data.getvalue()


ARCHIVE = bundle(("export.json", "{}"), ("ree/.git/HEAD", "ref\n"))
SERVED = hashlib.sha256(ARCHIVE).hexdigest()


class Stub:
    """The control plane's behaviour endpoints, serving canned answers."""

    def __init__(self) -> None:
        self.routes: dict[str, tuple[int, bytes]] = {
            "/api/v1/system/build-info": (200, b'{"version": "0.1.0", "revision": "abc123"}'),
            "/api/v1/behaviour/journals": (
                200,
                b'{"journals": [{"id": "api-000001", "process": "api", "epoch": 1, "last_seq": 2}]}',
            ),
            "/api/v1/behaviour/journals/api-000001": (200, JOURNAL),
            "/api/v1/behaviour/state": (
                200,
                json.dumps(
                    {
                        "cut": {"api-000001": [2, 2]},
                        "runs": {"build-1": {"run_id": "build-1", "ree_id": "ree-1", "status": "queued"}},
                        "allocations": None,
                    }
                ).encode(),
            ),
            "/api/v1/rees/ree-1/ree-archive": (200, ARCHIVE),
            # What the control plane served, and the journal positions around building each.
            "/api/v1/behaviour/archives": (
                200,
                json.dumps(
                    {
                        "archives": [
                            {"ree_id": "ree-1", "sha256": SERVED, "size": len(ARCHIVE), "cut": {"api-000001": [1, 2]}},
                            {"ree_id": "ree-2", "sha256": "0" * 64, "size": 1, "cut": {"api-000001": [2, 2]}},
                        ]
                    }
                ).encode(),
            ),
        }

    def answer(self, path: str) -> tuple[int, bytes]:
        return self.routes.get(path, (404, b'{"detail": "not found"}'))


@pytest.fixture
def stub() -> Iterator[tuple[Stub, str]]:
    served = Stub()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            status, body = served.answer(self.path.split("?")[0])
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield served, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_a_deployment_is_collected_through_its_control_plane(stub: tuple[Stub, str], tmp_path: Path) -> None:
    _, url = stub
    directory = tmp_path / "recording"
    start(directory, suite="demo")
    control_plane = ControlPlane(url)
    downloaded = download_archive(directory, control_plane, "ree-1")
    state, journals = collect_control_plane(directory, control_plane)

    assert downloaded.status == "recorded"
    assert downloaded.origin == f"{url}/api/v1/rees/ree-1/ree-archive"
    assert downloaded.cut == {"api-000001": (1, 2)}  # As the control plane recorded serving it.
    assert (state.status, state.cut) == ("recorded", {"api-000001": (2, 2)})
    assert journals.status == "recorded"
    assert (directory / "journal/api-000001.ndjson").read_bytes() == JOURNAL
    assert json.loads((directory / "stores/runs/build-1/state.json").read_text())["status"] == "queued"
    recording = read_recording(directory)
    assert (recording.control_plane, recording.build_revision) == (url, "abc123")

    evidence = load_recording(directory)
    sources = {source.id: source for source in evidence.sources}
    assert sources["api-000001"].origin == f"{url}/api/v1/behaviour/journals"
    assert sources["stores"].cut == {"api-000001": (2, 2)}
    # The journal's record is read back; how the checker reads the stored run is its own business.
    assert [event.key for event in evidence.events if event.source == "api-000001"] == ["build-1"]


def test_an_unreachable_control_plane_is_listed_not_skipped(tmp_path: Path) -> None:
    directory = tmp_path / "recording"
    assert main([str(directory), "--control-plane", "http://127.0.0.1:9", "--ree", "ree-1"]) == 1
    statuses = {(source.kind, source.status) for source in read_recording(directory).sources}
    assert statuses == {("git", "error"), ("state", "error"), ("journal", "error")}
    assert len(load_recording(directory).problems) == 3  # One per source, naming its origin.


def test_an_archive_the_control_plane_did_not_serve_is_an_error(stub: tuple[Stub, str], tmp_path: Path) -> None:
    served, url = stub
    served.routes["/api/v1/rees/ree-3/ree-archive"] = (200, bundle(("ree/.git/HEAD", "other\n")))
    directory = tmp_path / "recording"
    start(directory)
    source = download_archive(directory, ControlPlane(url), "ree-3")
    assert (source.status, source.problem) == ("error", "the control plane has no record of serving this archive")
    assert "404" in (download_archive(directory, ControlPlane(url), "ree-9").problem or "")


def test_archives_a_client_kept_are_placed_by_the_control_planes_record(stub: tuple[Stub, str], tmp_path: Path) -> None:
    _, url = stub
    kept = tmp_path / "playwright" / "demo-test"
    kept.mkdir(parents=True)
    (kept / "ree-hello-world.zip").write_bytes(ARCHIVE)
    (kept / "attachments").mkdir()
    (kept / "attachments" / "sealed-ree-bundle-1234.zip").write_bytes(ARCHIVE)  # The same archive, attached again.
    (kept / "trace.zip").write_bytes(bundle(("trace.json", "{}")))  # A browser trace: not served, passed over.
    (kept / "older-run.zip").write_bytes(bundle(("ree/.git/HEAD", "older\n")))  # Another run's: passed over.
    directory = tmp_path / "recording"
    start(directory)
    (source,) = kept_archives(directory, ControlPlane(url), [tmp_path / "playwright", tmp_path / "missing"])
    assert (source.name, source.status, source.cut) == ("ree-1", "recorded", {"api-000001": (1, 2)})
    assert source.origin == f"{url}/api/v1/rees/ree-1/ree-archive"
    assert (directory / "rees/ree-1/ree/.git/HEAD").is_file()


def test_archive_members_cannot_escape_the_recording(tmp_path: Path) -> None:
    directory = tmp_path / "recording"
    start(directory)
    zipped = tmp_path / "evil.zip"
    zipped.write_bytes(bundle(("../outside", "x")))
    source = archive(directory, zipped, cut=None, origin="x")
    assert source.problem == "unsafe archive member ../outside"
    assert not (tmp_path / "outside").exists()


def test_span_files_are_listed_and_copied_in_when_outside(tmp_path: Path) -> None:
    directory = tmp_path / "recording"
    start(directory)
    (directory / "telemetry").mkdir()
    (directory / "telemetry/api.ndjson").write_text("{}\n")
    (tmp_path / "location-1.ndjson").write_text("{}\n")
    listed = spans(directory, [directory / "telemetry/api.ndjson", tmp_path / "location-1.ndjson"], "local")
    assert [source.path for source in listed] == ["telemetry/api.ndjson", "telemetry/location-1.ndjson"]
    assert (directory / "telemetry/location-1.ndjson").is_file()


CLOSED = JOURNAL + record(3, kind="journal.closed", final=True)


def stopped_stack(tmp_path: Path) -> tuple[Path, Path, Path]:
    """The control state an API leaves behind once it stopped: journals, run store, allocation store."""
    journals, runs = tmp_path / "control/journal", tmp_path / "control/runs/build-1"
    journals.mkdir(parents=True)
    runs.mkdir(parents=True)
    (journals / "api-000001.ndjson").write_bytes(CLOSED)
    (journals / "ree-archives.ndjson").write_text("{}\n")  # The control plane's record of serving archives.
    (runs / "state.json").write_text(json.dumps({"run_id": "build-1", "status": "queued"}))
    (runs / "logs.jsonl").write_text("{}\n")
    allocations = tmp_path / "control/allocations.json"
    allocations.write_text("{}")
    return journals, runs.parent, allocations


def test_owners_exported_after_they_stopped_replace_the_live_snapshot(stub: tuple[Stub, str], tmp_path: Path) -> None:
    _, url = stub
    directory = tmp_path / "recording"
    start(directory)
    collect_control_plane(directory, ControlPlane(url))
    journals, runs, allocations = stopped_stack(tmp_path)

    journal, state = stopped_owners(directory, journals=journals, runs=runs, allocations=allocations)

    assert (journal.status, journal.cut) == ("recorded", None)
    assert (state.status, state.cut) == ("recorded", None)  # Taken after its owners stopped: must match exactly.
    assert sorted(path.name for path in (directory / "journal").iterdir()) == ["api-000001.ndjson"]
    assert (directory / "journal/api-000001.ndjson").read_bytes() == CLOSED
    assert sorted(path.name for path in (directory / "stores/runs/build-1").iterdir()) == ["state.json"]
    recording = read_recording(directory)
    assert [source.path for source in recording.sources].count("journal") == 1
    evidence = load_recording(directory)
    (source,) = [source for source in evidence.sources if source.kind == "journal"]
    assert (source.closed, source.final) == (True, True)


def test_an_export_without_journals_is_an_error(tmp_path: Path) -> None:
    directory = tmp_path / "recording"
    start(directory)
    (journal,) = stopped_owners(directory, journals=tmp_path / "missing", runs=None, allocations=None)
    assert journal.status == "error"
    assert "no journals" in str(journal.problem)


def test_the_cli_collects_archives_live_and_owners_after_they_stopped(stub: tuple[Stub, str], tmp_path: Path) -> None:
    _, url = stub
    directory = tmp_path / "recording"
    assert main([str(directory), "--control-plane", url, "--ree", "ree-1", "--skip-owners"]) == 0
    assert [source.kind for source in read_recording(directory).sources] == ["git"]
    journals, runs, allocations = stopped_stack(tmp_path)
    exported = [
        str(directory),
        "--journal-dir",
        str(journals),
        "--runs-dir",
        str(runs),
        "--allocations-file",
        str(allocations),
    ]
    assert main(exported) == 0
    recording = read_recording(directory)
    assert sorted(source.kind for source in recording.sources) == ["git", "journal", "state"]
    assert recording.build_revision == "abc123"

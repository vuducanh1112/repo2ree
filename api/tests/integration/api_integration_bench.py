"""What the api-integration tier runs against, and what it records.

Everything here is imported *by name* from the tier's test modules, which is
why it is not in ``conftest.py``: pytest imports every suite's ``conftest.py``
under the bare module name ``conftest``, so a ``from conftest import ...``
finds whichever one was imported last when tiers run together. A uniquely
named module cannot collide, the same reason
``core/tests/unit/scriptinfer_helpers.py`` is its own file.

The stack is the production one, as processes: uvicorn serving the API on a
real TCP port with its one event loop, a store registered and its token minted
with the API's own ``store_admin``, and a store workbench that dials
``/workbench/connect`` and runs the REEs' scripts on this host. Nothing is
mocked; a byte the workbench uploads beside its socket crosses real HTTP.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from repo2ree_testbed.artifacts import service_dir

_REPO_ROOT = Path(__file__).resolve().parents[3]

TEST_RESULTS_DIR = service_dir("api-integration")
TOOLS_BUNDLE = _REPO_ROOT / "dist" / "bundles" / "tools"
# The store every REE of this tier is created in.
STORE_ID = "itest-lab"

STARTUP_TIMEOUT_SECONDS = 60
# Hard per-request deadline. Every route the tier touches answers in well under
# a second when healthy; a stalled event loop blows this bound fast.
REQUEST_TIMEOUT = httpx.Timeout(30.0)


def tools_present() -> bool:
    return (TOOLS_BUNDLE / "manifest.json").is_file()


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "version"], capture_output=True, check=False).returncode == 0


@dataclass(frozen=True)
class Stack:
    base_url: str
    workbench_id: str


@contextmanager
def running_stack(state: Path, logs: Path) -> Iterator[Stack]:
    """The API and a store's workbench as real subprocesses, on throwaway state; stopped on exit."""
    logs.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = {
        **os.environ,
        "CONTROL_STATE_DIR": str(state / "control"),
        "UPLOAD_STAGING_DIR": str(state / "upload-staging"),
        "REE_INDEX_FILE": str(state / "ree-index.json"),
        "RUN_REGISTRY_DIR": str(state / "runs"),
        "BEHAVIOUR_JOURNAL_DIR": str(state / "journal"),
        "TRACE_FILE": str(logs / "traces.ndjson"),
    }
    token = _store_token(environment)
    workbench = [
        *(sys.executable, "-m", "repo2ree_workbench"),
        *("--store", f"{STORE_ID}={state / 'store'}", "--backend", "host"),
        *("--token", token, "--connect", f"ws://127.0.0.1:{port}/workbench/connect"),
        *(("--tools-bundle", str(TOOLS_BUNDLE)) if tools_present() else ()),
    ]
    with ExitStack() as stack:
        server_log = stack.enter_context((logs / "server.log").open("w"))
        workbench_log = stack.enter_context((logs / "workbench.log").open("w"))
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "repo2ree_api.main:app", "--host", "127.0.0.1", "--port", str(port)],
            env=environment,
            stdout=server_log,
            stderr=subprocess.STDOUT,
        )
        stack.callback(_stop, server)
        process = subprocess.Popen(
            workbench,
            env={**environment, "WORKBENCH_STATE_DIR": str(state / "workbench-state")},
            stdout=workbench_log,
            stderr=subprocess.STDOUT,
        )
        stack.callback(_stop, process)
        yield Stack(base_url, _served(base_url, (server, process)))


def _store_token(environment: dict[str, str]) -> str:
    """Register the store and mint its workbench's token, as an operator does on the service host."""

    def admin(*args: str) -> str:
        done = subprocess.run(
            [sys.executable, "-m", "repo2ree_api.store_admin", *args],
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout

    admin("add", STORE_ID, "--label", "API integration lab")
    return admin("token", STORE_ID).strip().splitlines()[-1]


def _served(base_url: str, processes: tuple[subprocess.Popen[bytes], ...]) -> str:
    """Block until the API answers and lists the store as served; the serving workbench's id."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("the API or the store's workbench exited before the store was served")
        try:
            response = httpx.get(f"{base_url}/api/v1/stores", timeout=2.0)
            stores = {store["store_id"]: store for store in response.json()["stores"]}
            if response.status_code == 200 and stores.get(STORE_ID, {}).get("connected"):
                return str(stores[STORE_ID]["workbench_id"])
        except (httpx.HTTPError, ValueError, KeyError):
            pass
        time.sleep(0.25)
    raise RuntimeError(f"store {STORE_ID!r} was not served within {STARTUP_TIMEOUT_SECONDS}s")


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ReeFilmstrip:
    """Records what the REE looked like after each authoring step.

    The trace tier answers what a run *did*; this answers what it left behind.
    Frames come from ``GET /rees/{id}/state``, which already carries the whole
    aggregate plus the audit derived from it — the audit being the point, since
    it is computed rather than stored and so exists nowhere a later reader could
    recover it. Never contents: a frame is a shape, and inlining every file
    would make the capture larger than the thing it describes.

    Labels are the caller's, because the interesting frames are named by intent
    ("build", "declare experiment") rather than by endpoint.
    """

    def __init__(self, client: httpx.Client, path: Path) -> None:
        self._client = client
        self._path = path
        self._index = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)

    def frame(self, ree_id: str, label: str) -> dict[str, Any]:
        response = self._client.get(f"/api/v1/rees/{ree_id}/state")
        assert response.status_code == 200, f"filmstrip frame {label!r}: {response.text}"
        state: dict[str, Any] = response.json()
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"index": self._index, "label": label, "state": state}) + "\n")
        self._index += 1
        return state

"""A client of a running deployment's public API, for the system suite.

Everything goes through HTTP, as any client's requests would: the suite holds
no in-process handle on the stack it drives. Imported by name from the test
modules (a uniquely named module, so it cannot collide with another tier's
``conftest``).
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest

from repo2ree_testbed.faults import FAULTS_URL, Fault, inject
from repo2ree_testbed.run_watch import INSTANT_RUN, NETWORK_RUN, RunWatch, settle_run
from repo2ree_testbed.showcases import INSTANT, SOURCE, Project, RecipeScript
from repo2ree_testbed.showcases import RESULT as RESULT
from repo2ree_testbed.stack.store_images import PYTHON_SLIM_IMAGE

ROOT = Path(__file__).resolve().parents[3]
BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT = "ree-scripts/build_experiment_environment.sh"
ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT = "ree-scripts/activate_experiment_environment.sh"

# A bench without a Docker daemon: the base image is the experiment environment environment.
# Same pin as the GUI suite's lightweight bench (gui/tests/helpers/flow.ts).
LIGHTWEIGHT_IMAGE = PYTHON_SLIM_IMAGE
TERMINAL = frozenset({"succeeded", "failed", "canceled"})
# Where a store runs the scripts of the REEs it keeps: in a container from each REE's image, or on its host.
STORE_BACKEND = os.environ.get("E2E_STORE_BACKEND", "container")


# The instant project's names, as most suites use it.
PROJECT = INSTANT.source
PROJECT_DIR = SOURCE
EXPERIMENT_ENVIRONMENT = INSTANT.experiment_environment_path
EXPERIMENT = INSTANT.experiment
EXPERIMENT_SCRIPT = INSTANT.experiment_script
EXPERIMENT_VERIFY = INSTANT.experiment_verify


def recipe(name: RecipeScript) -> str:
    return INSTANT.recipe(name)


def project_archive() -> bytes:
    return INSTANT.archive()


# How long a workbench whose network came back takes to reconnect: a ping unanswered (40s), the close
# handshake (10s), the pause before dialing (3s), and the dial (10s), and some margin.
RECONNECT_BOUND = 78


class ApiError(AssertionError):
    pass


@dataclass
class Api:
    base_url: str
    archive_dir: Path
    http: httpx.Client = field(init=False)

    def __post_init__(self) -> None:
        self.http = httpx.Client(base_url=self.base_url, timeout=60.0)

    def request(self, method: str, path: str, *, expect: int | None = 200, **kwargs: Any) -> httpx.Response:
        response = self.http.request(method, path, **kwargs)
        if expect is not None and response.status_code != expect:
            raise ApiError(f"{method} {path} -> {response.status_code}: {response.text[:800]}")
        return response

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs).json()

    def post(self, path: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return self.request("POST", path, json=payload or {}, **kwargs).json()

    # ---- runs ---------------------------------------------------------------

    def wait(
        self,
        ree_id: str,
        run: dict[str, Any] | str,
        timeout: float | None = None,
        *,
        watch: RunWatch = INSTANT_RUN,
    ) -> dict[str, Any]:
        """Wait for a background run to settle and return it; see :func:`settle_run`.

        An explicit ``timeout`` is for a run expected to go quiet, a frozen or lost
        workbench above all: it bounds the whole wait and nothing else.
        """
        run_id = run if isinstance(run, str) else run["run_id"]
        if timeout is not None:
            watch = RunWatch.silent(timeout)
        return settle_run(lambda path, params: self.get(path, params=params), ree_id, run_id, watch).run

    def wait_for_status(self, ree_id: str, run_id: str, *statuses: str, timeout: float = 60.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self.get(f"/api/v1/rees/{ree_id}/runs/{run_id}")
            if run["status"] in statuses:
                return dict(run)
            time.sleep(0.1)
        raise ApiError(f"run {run_id} never reached {statuses}")

    def logs(self, ree_id: str, run_id: str) -> str:
        entries = self.get(f"/api/v1/rees/{ree_id}/runs/{run_id}/logs").get("entries", [])
        return "\n".join(f"[{entry.get('level')}] {entry.get('message')}" for entry in entries[-30:])

    def stage(
        self, ree_id: str, path: str, payload: dict[str, Any] | None = None, *, watch: RunWatch = INSTANT_RUN
    ) -> dict[str, Any]:
        """Start a background stage and wait for it to settle, whatever its outcome."""
        return self.wait(ree_id, self.post(f"/api/v1/rees/{ree_id}/{path}", payload), watch=watch)

    def succeed(
        self, ree_id: str, path: str, payload: dict[str, Any] | None = None, *, watch: RunWatch = INSTANT_RUN
    ) -> dict[str, Any]:
        run = self.stage(ree_id, path, payload, watch=watch)
        if run["status"] != "succeeded":
            raise ApiError(f"{path} ended {run['status']}\n{self.logs(ree_id, run['run_id'])}")
        return run

    # ---- REE lifecycle ------------------------------------------------------

    def store(self) -> str:
        """The first store a workbench serves now."""
        served = [store["store_id"] for store in self.get("/api/v1/stores")["stores"] if store["connected"]]
        if not served:
            raise ApiError("no workbench serves a store")
        return str(served[0])

    def create(self, name: str, *, image: str | None = LIGHTWEIGHT_IMAGE, location: str | None = None) -> str:
        """A new REE in a store (the first served, or ``location``), declaring ``image`` from the store's
        offer, or its host when the store runs scripts there."""
        store = {"name": name, "store_id": location or self.store()}
        created = self.post("/api/v1/rees", {**store, "image": image} if STORE_BACKEND == "container" else store)
        ree_id = str(created["ree_id"])
        provisioned = self.wait(ree_id, created, watch=NETWORK_RUN)
        if provisioned["status"] != "succeeded":
            raise ApiError(f"provisioning ended {provisioned['status']}\n{self.logs(ree_id, created['run_id'])}")
        return ree_id

    def keep_archive(self, ree_id: str, label: str) -> Path | None:
        """Download the REE as its owner would and keep it where the collector looks; None if refused.

        A bench reconnecting after a fault answers 503 (retryable) until it is back; wait it out.
        """
        deadline = time.monotonic() + RECONNECT_BOUND
        while True:
            response = self.request("GET", f"/api/v1/rees/{ree_id}/ree-archive", expect=None, timeout=120.0)
            if response.status_code != 503 or time.monotonic() > deadline:
                break
            time.sleep(1)
        if response.status_code != 200:
            return None
        target = self.archive_dir / f"{label}-{ree_id}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return target

    def release(self, ree_id: str) -> None:
        self.request("DELETE", f"/api/v1/rees/{ree_id}", expect=None)

    # ---- authoring ----------------------------------------------------------

    def upload_source(self, ree_id: str, data: bytes, name: str = INSTANT.upload_name) -> dict[str, Any]:
        upload = self.post(
            f"/api/v1/rees/{ree_id}/source:upload-init",
            {"file_name": name, "size": len(data), "content_type": "application/gzip"},
        )
        self.request("PUT", upload["upload_url"], content=data)
        run = self.post(
            f"/api/v1/rees/{ree_id}/source:upload-complete",
            {"upload_token": upload["upload_token"], "archive_name": name},
        )
        return self.wait(ree_id, run)

    def write(self, ree_id: str, path: str, content: str, *, expect: int | None = 200) -> httpx.Response:
        return self.request(
            "PUT", f"/api/v1/rees/{ree_id}/files/content", json={"path": path, "content": content}, expect=expect
        )

    def patch(self, ree_id: str, patch: dict[str, Any], *, expect: int | None = 200) -> httpx.Response:
        return self.request(
            "PATCH", f"/api/v1/rees/{ree_id}/definition", json={"definition_patch": patch}, expect=expect
        )

    def infer(self, ree_id: str, kind: str, **selector: str) -> dict[str, Any]:
        report = self.post(
            f"/api/v1/rees/{ree_id}/script-inferences:generate", {"targets": [{"kind": kind, **selector}]}
        )
        return dict(report["results"][0])

    def ree(self, ree_id: str) -> dict[str, Any]:
        return dict(self.get(f"/api/v1/rees/{ree_id}")["ree"])

    def audit(self, ree_id: str) -> dict[str, Any]:
        return dict(self.get(f"/api/v1/rees/{ree_id}/state")["audit"])

    def seal(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> dict[str, Any]:
        payload = {"include_source": True, "include_experiment_environment": True, "include_results": True}
        return self.stage(ree_id, "ree:seal", payload, watch=watch)

    def load(self, ree_id: str, bundle: bytes) -> None:
        """Seat a sealed REE's archive in ``ree_id``, as a reviewer does."""
        upload = self.post(
            f"/api/v1/rees/{ree_id}/ree:upload-init",
            {"file_name": "ree.zip", "size": len(bundle), "content_type": "application/zip"},
        )
        self.request("PUT", upload["upload_url"], content=bundle)
        self.succeed(ree_id, "ree:load", {"upload_token": upload["upload_token"], "archive_name": "ree.zip"})

    # ---- a fixture project, step by step ------------------------------------

    def acquire(self, ree_id: str, fixture: Project = INSTANT) -> None:
        run = self.upload_source(ree_id, fixture.archive(), fixture.upload_name)
        if run["status"] != "succeeded":
            raise ApiError(f"source ended {run['status']}\n{self.logs(ree_id, run['run_id'])}")

    def build_experiment_environment(
        self, ree_id: str, script: str | None = None, fixture: Project = INSTANT
    ) -> dict[str, Any]:
        """Declare the experiment environment, author its build (inferred unless given or brought), and run it."""
        self.patch(ree_id, {"experiment_environment": {"artifact_path": fixture.experiment_environment_path}})
        if script is None and not fixture.infer_build:
            script = fixture.recipe("build_experiment_environment.sh")
        if script is None:
            result = self.infer(ree_id, "build_experiment_environment")
            script = str(result["candidates"][0]["body"])
        self.write(ree_id, BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, script)
        self.write(ree_id, ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, fixture.recipe("activate_experiment_environment.sh"))
        return self.stage(ree_id, "build-experiment-environment", watch=fixture.watch)

    def activate(self, ree_id: str, script: str | None = None, fixture: Project = INSTANT) -> dict[str, Any]:
        """Test the activation alone; with ``script``, after writing it as the activate script."""
        if script is not None:
            self.write(ree_id, ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, script)
        return self.stage(ree_id, "activation-test", watch=fixture.watch)

    def experiment(
        self, ree_id: str, *, run: str | None = None, verify: str | None = None, fixture: Project = INSTANT
    ) -> dict[str, Any]:
        self.write(ree_id, fixture.experiment_script, run or fixture.recipe("experiment.sh"))
        self.write(ree_id, fixture.experiment_verify, verify or fixture.recipe("experiment.verify.sh"))
        self.patch(ree_id, {"experiments": [{"name": fixture.experiment, "output_paths": list(fixture.outputs)}]})
        return self.stage(ree_id, f"experiments/{fixture.experiment}:run", watch=fixture.watch)

    def author(self, ree_id: str, fixture: Project = INSTANT) -> None:
        """Every authoring stage of a fixture project, each required to succeed."""
        self.acquire(ree_id, fixture)
        self.succeed(ree_id, "evaluate", watch=fixture.watch)
        self.succeed(ree_id, "generate-hbom")
        steps = (
            ("build_experiment_environment", self.build_experiment_environment(ree_id, fixture=fixture)),
            ("activation", self.activate(ree_id, fixture=fixture)),
        )
        for label, run in steps:
            if run["status"] != "succeeded":
                raise ApiError(f"{label} ended {run['status']}\n{self.logs(ree_id, run['run_id'])}")
        run = self.experiment(ree_id, fixture=fixture)
        if run["status"] != "succeeded":
            raise ApiError(f"experiment ended {run['status']}\n{self.logs(ree_id, run['run_id'])}")


def fault(injected: Fault) -> None:
    """Ask the stack this suite runs on to inject a fault, now."""
    inject(os.environ[FAULTS_URL], injected)


# ---- fixtures every suite on a stack shares -----------------------------------

BASE_URL = os.environ.get("E2E_API_BASE_URL", "")
ARCHIVE_DIR = Path(os.environ.get("E2E_ARCHIVE_DIR", "test-artifacts/python/system/archives"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if BASE_URL:
        return
    skip = pytest.mark.skip(reason="the system suite drives a running stack: run it with just test-e2e-system")
    for item in items:
        item.add_marker(skip)


@pytest.fixture(scope="session")
def api() -> Api:
    return Api(BASE_URL.rstrip("/"), ARCHIVE_DIR)


@pytest.fixture
def new_ree(api: Api, request: pytest.FixtureRequest) -> Iterator[Callable[..., str]]:
    """Create REEs on demand; each is downloaded, then released, when the test ends."""
    created: list[str] = []
    label = re.sub(r"[^a-z0-9]+", "-", request.node.name.lower()).strip("-")

    def create(name: str = label, **kwargs: str | None) -> str:
        ree_id: str = api.create(name[:60], **kwargs)
        created.append(ree_id)
        return ree_id

    yield create
    for ree_id in created:
        api.keep_archive(ree_id, label)
        api.release(ree_id)

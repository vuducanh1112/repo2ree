"""A client of a running deployment's public API, for the system suite.

Everything goes through HTTP, as any client's requests would: the suite holds
no in-process handle on the stack it drives. Imported by name from the test
modules (a uniquely named module, so it cannot collide with another tier's
``conftest``).
"""

from __future__ import annotations

import io
import os
import re
import tarfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest

from repo2ree_testbed.faults import FAULTS_URL, Fault, inject
from repo2ree_testbed.run_watch import INSTANT_RUN, NETWORK_RUN, RunWatch, settle_run

ROOT = Path(__file__).resolve().parents[3]
RESULT = "result.txt"
BUILD_SCRIPT = "ree-scripts/build_script.sh"
ACTIVATION_SCRIPT = "ree-scripts/activation.sh"

# A bench without a Docker daemon: the base image is the runtime environment.
# Same pin as the GUI suite's lightweight bench (gui/tests/helpers/flow.ts).
LIGHTWEIGHT_IMAGE = os.environ.get(
    "PYTHON_SLIM_IMAGE",
    "docker.io/library/python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534",
)
# A bench with its own Docker daemon: the provider's default image.
DIND_IMAGE = os.environ.get(
    "DIND_IMAGE",
    "docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6f61cacb880de2186339a524ecba1ce098dbbaceed6515",
)
TERMINAL = frozenset({"succeeded", "failed", "canceled"})


@dataclass(frozen=True)
class Fixture:
    """A project an REE is authored from: its recipes, what its build produces, and the bench it needs.

    Both fixtures need nothing downloaded. ``INSTANT`` runs on a bench without a Docker
    daemon, its runtime a packed venv; ``INSTANT_DOCKER`` runs on a dind bench, its
    runtime an image the bench's own daemon builds FROM scratch.
    """

    project: Path
    runtime: str
    experiment: str
    image: str
    # Whether the build script is the one script inference proposes, or the recipe's.
    infer_build: bool

    @property
    def name(self) -> str:
        return self.project.name

    @property
    def experiment_script(self) -> str:
        return f"ree-scripts/experiments/{self.experiment}.sh"

    @property
    def experiment_verify(self) -> str:
        return f"ree-scripts/experiments/{self.experiment}.verify.sh"

    def recipe(self, name: str) -> str:
        return (ROOT / "examples/recipes" / self.name / name).read_text()

    def archive(self) -> bytes:
        """The project packed as an upload, without interpreter caches."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            archive.add(
                self.project, arcname=self.name, filter=lambda info: None if "__pycache__" in info.name else info
            )
        return buffer.getvalue()


INSTANT = Fixture(
    project=ROOT / "examples/projects/instant_hello_world",
    runtime="instant_hello_world/runtime-venv.tar.gz",
    experiment="instant-hello",
    image=LIGHTWEIGHT_IMAGE,
    infer_build=True,
)
INSTANT_DOCKER = Fixture(
    project=ROOT / "examples/projects/instant_docker_hello_world",
    runtime="instant_docker_hello_world/runtime-image.tar",
    experiment="instant-docker-hello",
    image=DIND_IMAGE,
    # Inference proposes `docker build` of the project as it stands; the recipe also
    # brings the bench's busybox into the build context, which a FROM scratch image needs.
    infer_build=False,
)

# The instant fixture's names, as most suites use it.
PROJECT = INSTANT.project
PROJECT_DIR = INSTANT.name
RUNTIME = INSTANT.runtime
EXPERIMENT = INSTANT.experiment
EXPERIMENT_SCRIPT = INSTANT.experiment_script
EXPERIMENT_VERIFY = INSTANT.experiment_verify


def recipe(name: str) -> str:
    return INSTANT.recipe(name)


def project_archive() -> bytes:
    return INSTANT.archive()


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

    def stage(self, ree_id: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a background stage and wait for it to settle, whatever its outcome."""
        return self.wait(ree_id, self.post(f"/api/v1/rees/{ree_id}/{path}", payload))

    def succeed(self, ree_id: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        run = self.stage(ree_id, path, payload)
        if run["status"] != "succeeded":
            raise ApiError(f"{path} ended {run['status']}\n{self.logs(ree_id, run['run_id'])}")
        return run

    # ---- REE lifecycle ------------------------------------------------------

    def location(self) -> str:
        locations = self.get("/api/v1/compute-locations")["locations"]
        if not locations:
            raise ApiError("no compute location is connected")
        return str(locations[0]["id"])

    def create(self, name: str, *, image: str = LIGHTWEIGHT_IMAGE, location: str | None = None) -> str:
        created = self.post("/api/v1/rees", {"name": name, "location_id": location or self.location(), "image": image})
        ree_id = str(created["ree_id"])
        provisioned = self.wait(ree_id, created, watch=NETWORK_RUN)
        if provisioned["status"] != "succeeded":
            raise ApiError(f"provisioning ended {provisioned['status']}\n{self.logs(ree_id, created['run_id'])}")
        return ree_id

    def keep_archive(self, ree_id: str, label: str) -> Path | None:
        """Download the REE as its owner would and keep it where the collector looks; None if refused.

        A bench reconnecting after a fault answers 503 (retryable) for a few seconds; wait it out.
        """
        deadline = time.monotonic() + 30
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

    def upload_source(self, ree_id: str, data: bytes, name: str = "instant-hello-world.tar.gz") -> dict[str, Any]:
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

    def seal(self, ree_id: str) -> dict[str, Any]:
        payload = {"include_source": True, "include_runtime": True, "include_results": True}
        return self.stage(ree_id, "ree:seal", payload)

    # ---- a fixture project, step by step ------------------------------------

    def acquire(self, ree_id: str, fixture: Fixture = INSTANT) -> None:
        run = self.upload_source(ree_id, fixture.archive(), f"{fixture.name.replace('_', '-')}.tar.gz")
        if run["status"] != "succeeded":
            raise ApiError(f"source ended {run['status']}\n{self.logs(ree_id, run['run_id'])}")

    def build(self, ree_id: str, script: str | None = None, fixture: Fixture = INSTANT) -> dict[str, Any]:
        """Declare the runtime, author the build (inferred unless given or the fixture brings one), and run it."""
        self.patch(ree_id, {"build_runtime": {"runtime_path": fixture.runtime}})
        if script is None and not fixture.infer_build:
            script = fixture.recipe("build_script.sh")
        if script is None:
            result = self.infer(ree_id, "build")
            script = str(result["candidates"][0]["body"])
        self.write(ree_id, BUILD_SCRIPT, script)
        return self.stage(ree_id, "build-runtime")

    def activate(self, ree_id: str, script: str | None = None, fixture: Fixture = INSTANT) -> dict[str, Any]:
        self.write(ree_id, ACTIVATION_SCRIPT, script or fixture.recipe("activation.sh"))
        self.patch(ree_id, {"test_activation": {}})
        return self.stage(ree_id, "activation-test")

    def experiment(
        self, ree_id: str, *, run: str | None = None, verify: str | None = None, fixture: Fixture = INSTANT
    ) -> dict[str, Any]:
        self.write(ree_id, fixture.experiment_script, run or fixture.recipe("experiment.sh"))
        self.write(ree_id, fixture.experiment_verify, verify or fixture.recipe("experiment.verify.sh"))
        self.patch(ree_id, {"experiments": [{"name": fixture.experiment, "output_paths": [RESULT]}]})
        return self.stage(ree_id, f"experiments/{fixture.experiment}:run")

    def author(self, ree_id: str, fixture: Fixture = INSTANT) -> None:
        """Every authoring stage of a fixture project, each required to succeed."""
        self.acquire(ree_id, fixture)
        self.succeed(ree_id, "evaluate")
        self.succeed(ree_id, "generate-hbom")
        steps = (("build", self.build(ree_id, fixture=fixture)), ("activation", self.activate(ree_id, fixture=fixture)))
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

    def create(name: str = label, **kwargs: str) -> str:
        ree_id: str = api.create(name[:60], **kwargs)
        created.append(ree_id)
        return ree_id

    yield create
    for ree_id in created:
        api.keep_archive(ree_id, label)
        api.release(ree_id)

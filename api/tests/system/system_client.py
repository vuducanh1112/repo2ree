"""A client of a running deployment's public API, for the system suite.

Everything goes through HTTP, as any client's requests would: the suite holds
no in-process handle on the stack it drives. Imported by name from the test
modules (a uniquely named module, so it cannot collide with another tier's
``conftest``).
"""

from __future__ import annotations

import io
import os
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "examples/projects/instant_hello_world"
RECIPES = ROOT / "examples/recipes/instant_hello_world"
PROJECT_DIR = PROJECT.name
RUNTIME = f"{PROJECT_DIR}/runtime-venv.tar.gz"
EXPERIMENT = "instant-hello"
RESULT = "result.txt"

BUILD_SCRIPT = "ree-scripts/build_script.sh"
ACTIVATION_SCRIPT = "ree-scripts/activation.sh"
EXPERIMENT_SCRIPT = f"ree-scripts/experiments/{EXPERIMENT}.sh"
EXPERIMENT_VERIFY = f"ree-scripts/experiments/{EXPERIMENT}.verify.sh"

# A bench without a Docker daemon: the base image is the runtime environment.
# Same pin as the GUI suite's lightweight bench (gui/tests/e2e/helpers/flow.ts).
LIGHTWEIGHT_IMAGE = os.environ.get(
    "PYTHON_SLIM_IMAGE",
    "docker.io/library/python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534",
)
TERMINAL = frozenset({"succeeded", "failed", "canceled"})
RUN_TIMEOUT = 180.0


def recipe(name: str) -> str:
    return (RECIPES / name).read_text()


def project_archive() -> bytes:
    """The project packed as an upload, without interpreter caches."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        archive.add(PROJECT, arcname=PROJECT_DIR, filter=lambda info: None if "__pycache__" in info.name else info)
    return buffer.getvalue()


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

    def wait(self, ree_id: str, run: dict[str, Any] | str, timeout: float = RUN_TIMEOUT) -> dict[str, Any]:
        """Poll a background run until it settles; return the settled run."""
        run_id = run if isinstance(run, str) else run["run_id"]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            settled = self.get(f"/api/v1/rees/{ree_id}/runs/{run_id}")
            if settled["status"] in TERMINAL:
                return dict(settled)
            time.sleep(0.2)
        raise ApiError(f"run {run_id} did not settle within {timeout:.0f}s")

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
        provisioned = self.wait(ree_id, created)
        if provisioned["status"] != "succeeded":
            raise ApiError(f"provisioning ended {provisioned['status']}\n{self.logs(ree_id, created['run_id'])}")
        return ree_id

    def keep_archive(self, ree_id: str, label: str) -> Path | None:
        """Download the REE as its owner would and keep it where the collector looks; None if refused."""
        response = self.request("GET", f"/api/v1/rees/{ree_id}/ree-archive", expect=None, timeout=120.0)
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

    # ---- the instant project, step by step ----------------------------------

    def acquire(self, ree_id: str) -> None:
        run = self.upload_source(ree_id, project_archive())
        if run["status"] != "succeeded":
            raise ApiError(f"source ended {run['status']}\n{self.logs(ree_id, run['run_id'])}")

    def build(self, ree_id: str, script: str | None = None) -> dict[str, Any]:
        """Declare the runtime, author the build (inferred unless given), and run it."""
        self.patch(ree_id, {"build_runtime": {"runtime_path": RUNTIME}})
        if script is None:
            result = self.infer(ree_id, "build")
            script = str(result["candidates"][0]["body"])
        self.write(ree_id, BUILD_SCRIPT, script)
        return self.stage(ree_id, "build-runtime")

    def activate(self, ree_id: str, script: str | None = None) -> dict[str, Any]:
        self.write(ree_id, ACTIVATION_SCRIPT, script or recipe("activation.sh"))
        self.patch(ree_id, {"test_activation": {}})
        return self.stage(ree_id, "activation-test")

    def experiment(self, ree_id: str, *, run: str | None = None, verify: str | None = None) -> dict[str, Any]:
        self.write(ree_id, EXPERIMENT_SCRIPT, run or recipe("experiment.sh"))
        self.write(ree_id, EXPERIMENT_VERIFY, verify or recipe("experiment.verify.sh"))
        self.patch(ree_id, {"experiments": [{"name": EXPERIMENT, "output_paths": [RESULT]}]})
        return self.stage(ree_id, f"experiments/{EXPERIMENT}:run")

    def author(self, ree_id: str) -> None:
        """Every authoring stage of the instant project, each required to succeed."""
        self.acquire(ree_id)
        self.succeed(ree_id, "evaluate")
        self.succeed(ree_id, "generate-hbom")
        for label, run in (("build", self.build(ree_id)), ("activation", self.activate(ree_id))):
            if run["status"] != "succeeded":
                raise ApiError(f"{label} ended {run['status']}\n{self.logs(ree_id, run['run_id'])}")
        run = self.experiment(ree_id)
        if run["status"] != "succeeded":
            raise ApiError(f"experiment ended {run['status']}\n{self.logs(ree_id, run['run_id'])}")

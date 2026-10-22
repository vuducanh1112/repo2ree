"""Seeded random author sessions, with faults between the steps.

Each seed is one session on a fresh stack, and the same seed replays the same
steps. The API must answer every request without a server error and settle every
run it starts; the behaviour check judges what the owners recorded meanwhile.
The steps a session took are kept in its test directory as chaos.json.
"""

from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from system_client import (
    ACTIVATION_SCRIPT,
    BUILD_SCRIPT,
    EXPERIMENT,
    EXPERIMENT_SCRIPT,
    EXPERIMENT_VERIFY,
    RESULT,
    RUNTIME,
    Api,
    fault,
    project_archive,
    recipe,
)

from repo2ree_testbed.faults import (
    CrashApi,
    FaultRefusedError,
    HealWorkbench,
    KillWorkbench,
    PartitionWorkbench,
    PauseWorkbench,
    ResumeWorkbench,
)

SEEDS = int(os.environ.get("CHAOS_SEEDS", "4"))
STEPS = int(os.environ.get("CHAOS_STEPS", "12"))
FAILING_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'resolving dependencies'\nexit 3\n"
SLOW_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'building slowly'\nsleep 60\n"
# The order an author works in; a session favours the next stage, so faults land in deep authoring too.
PIPELINE = ("source", "evaluate", "hbom", "build", "activate", "experiment", "seal")


class ServerError(AssertionError):
    pass


@dataclass
class Step:
    name: str
    outcome: str
    seconds: float


class Session:
    def __init__(self, api: Api, new_ree: Callable[..., str], rng: random.Random) -> None:
        self.api = api
        self.new_ree = new_ree
        self.rng = rng
        self.ree_id = new_ree()
        self.dead = False
        self.progress = 0
        self.steps: list[Step] = []

    def call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response: httpx.Response = self.api.request(method, path, expect=None, **kwargs)
        if response.status_code >= 500 and response.status_code != 503:
            raise ServerError(f"{method} {path} -> {response.status_code}: {response.text[:400]}")
        return response

    def ree(self, path: str) -> str:
        return f"/api/v1/rees/{self.ree_id}/{path}"

    def stage(self, path: str, payload: dict[str, Any] | None = None) -> str:
        response = self.call("POST", self.ree(path), json=payload or {})
        if response.status_code != 200:
            return f"refused {response.status_code}"
        return str(self.api.wait(self.ree_id, response.json())["status"])

    def write(self, path: str, content: str) -> None:
        self.call("PUT", self.ree("files/content"), json={"path": path, "content": content})

    def patch(self, patch: dict[str, Any]) -> None:
        self.call("PATCH", self.ree("definition"), json={"definition_patch": patch})

    def bench(self) -> str | None:
        allocations = self.call("GET", "/api/v1/allocations").json()["allocations"]
        found = [item for item in allocations if item["request"]["ree_id"] == self.ree_id]
        return str(found[0]["request"]["allocation_id"]) if found and found[0]["state"] == "assigned" else None

    # ---- authoring --------------------------------------------------------------

    def source(self) -> str:
        data = project_archive()
        name = "instant-hello-world.tar.gz"
        init = {"file_name": name, "size": len(data), "content_type": "application/gzip"}
        upload = self.call("POST", self.ree("source:upload-init"), json=init)
        if upload.status_code != 200:
            return f"refused {upload.status_code}"
        ticket = upload.json()
        self.call("PUT", ticket["upload_url"], content=data)
        done = {"upload_token": ticket["upload_token"], "archive_name": name}
        return self.stage("source:upload-complete", done)

    def build(self, script: str) -> str:
        self.patch({"build_runtime": {"runtime_path": RUNTIME}})
        self.write(BUILD_SCRIPT, script)
        return self.stage("build-runtime")

    def canceled_build(self) -> str:
        self.patch({"build_runtime": {"runtime_path": RUNTIME}})
        self.write(BUILD_SCRIPT, SLOW_BUILD)
        started = self.call("POST", self.ree("build-runtime"), json={})
        if started.status_code != 200:
            return f"refused {started.status_code}"
        run = started.json()
        time.sleep(self.rng.uniform(0, 5))
        self.call("POST", self.ree(f"runs/{run['run_id']}:cancel"), json={})
        return str(self.api.wait(self.ree_id, run)["status"])

    def activate(self) -> str:
        self.write(ACTIVATION_SCRIPT, recipe("activation.sh"))
        self.patch({"test_activation": {}})
        return self.stage("activation-test")

    def experiment(self) -> str:
        self.write(EXPERIMENT_SCRIPT, recipe("experiment.sh"))
        self.write(EXPERIMENT_VERIFY, recipe("experiment.verify.sh"))
        self.patch({"experiments": [{"name": EXPERIMENT, "output_paths": [RESULT]}]})
        return self.stage(f"experiments/{EXPERIMENT}:run")

    def seal(self) -> str:
        return self.stage("ree:seal", {"include_source": True, "include_runtime": True, "include_results": True})

    def download(self) -> str:
        return "kept" if self.api.keep_archive(self.ree_id, f"chaos-{len(self.steps)}") else "refused"

    # ---- faults -----------------------------------------------------------------

    def interrupt(self, start: Callable[[str], Any], end: Callable[[str], Any]) -> str:
        bench = self.bench()
        if bench is None:
            return "no bench"
        try:
            fault(start(bench))
            time.sleep(self.rng.uniform(2, 10))
            fault(end(bench))
        except FaultRefusedError as refused:
            return f"refused: {refused}"
        return "injected"

    def kill(self) -> str:
        bench = self.bench()
        if bench is None:
            return "no bench"
        fault(KillWorkbench(allocation_id=bench))
        self.dead = True
        return "injected"

    def crash_api(self) -> str:
        fault(CrashApi())
        return "injected"

    def replace(self) -> str:
        self.call("DELETE", f"/api/v1/rees/{self.ree_id}")
        self.ree_id = self.new_ree()
        self.dead = False
        self.progress = 0
        return "replaced"

    # ---- the session ------------------------------------------------------------

    def choices(self) -> dict[str, tuple[int, Callable[[], str]]]:
        return {
            "source": (3, self.source),
            "evaluate": (3, lambda: self.stage("evaluate")),
            "hbom": (2, lambda: self.stage("generate-hbom")),
            "build": (3, lambda: self.build(recipe("build_script.sh"))),
            "failing build": (1, lambda: self.build(FAILING_BUILD)),
            "canceled build": (1, self.canceled_build),
            "activate": (2, self.activate),
            "experiment": (2, self.experiment),
            "seal": (1, self.seal),
            "download": (1, self.download),
            "pause": (
                1,
                lambda: self.interrupt(
                    lambda b: PauseWorkbench(allocation_id=b), lambda b: ResumeWorkbench(allocation_id=b)
                ),
            ),
            "partition": (
                1,
                lambda: self.interrupt(
                    lambda b: PartitionWorkbench(allocation_id=b), lambda b: HealWorkbench(allocation_id=b)
                ),
            ),
            "kill": (1, self.kill),
            "crash api": (1, self.crash_api),
            "replace": (6 if self.dead else 0, self.replace),
        }

    def run(self, steps: int) -> None:
        for _ in range(steps):
            choices = self.choices()
            following = PIPELINE[self.progress] if self.progress < len(PIPELINE) else None
            weights = [weight * (8 if name == following else 1) for name, (weight, _) in choices.items()]
            name = self.rng.choices(list(choices), weights=weights)[0]
            started = time.monotonic()
            outcome = choices[name][1]()
            if name == following and outcome == "succeeded":
                self.progress += 1
            self.steps.append(Step(name, outcome, round(time.monotonic() - started, 1)))
            print(f"   {name:<15} {outcome}")


@pytest.mark.parametrize("seed", range(SEEDS), ids=lambda seed: f"seed-{seed}")
def test_a_random_session_keeps_the_api_answering(api: Api, new_ree: Callable[..., str], seed: int) -> None:
    session = Session(api, new_ree, random.Random(seed))  # noqa: S311 - a replayable session, not a secret
    try:
        session.run(STEPS)
    finally:
        if directory := os.environ.get("E2E_TEST_DIR"):
            log = Path(directory) / "chaos.json"
            log.write_text(json.dumps({"seed": seed, "steps": [asdict(step) for step in session.steps]}, indent=2))

"""One source stack: the API under coverage, its compute locations, one client run, and what it leaves."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from repo2ree_testbed.artifacts import ROOT, run_dir, write_provenance
from repo2ree_testbed.python_coverage import CoverageRoot, render
from repo2ree_testbed.records import RecordingManifest, read
from repo2ree_testbed.stack.clients import Client, Launch, Started
from repo2ree_testbed.stack.process import listed, reachable, terminate, wait_until
from repo2ree_testbed.stack.services import Deployment, backend_environment, locations
from repo2ree_testbed.stack.workbench_cleanup import cleanup


@dataclass(frozen=True)
class Layout:
    directory: Path
    test: str | None
    collector: bool
    client_log: Path | None
    run_token: str

    @classmethod
    def for_test(cls, tier: str, directory: Path, test: str | None, *, collector: bool, client_log: bool) -> Layout:
        log = directory / "logs/client.log" if client_log else None
        return cls(directory, test, collector, log, f"e2e-{tier}-{uuid.uuid4().hex}")

    @property
    def logs(self) -> Path:
        return self.directory / "logs"

    @property
    def recording(self) -> Path:
        return self.directory / "recording"

    @property
    def archives(self) -> Path:
        return self.directory / "artifacts/archives"

    @property
    def output(self) -> Path:
        return self.directory / "artifacts"

    @property
    def telemetry(self) -> Path | None:
        return None if self.collector else self.recording / "telemetry"

    def rees(self) -> tuple[str, ...]:
        manifest = read(RecordingManifest, self.recording / "manifest.json")
        return manifest.rees() if manifest else ()


class E2EStack:
    def __init__(
        self,
        deployment: Deployment,
        client: Client,
        layout: Layout,
        selection: Sequence[str],
        *,
        revision: str,
        fresh_coverage: bool,
    ) -> None:
        self.deployment = deployment
        self.client = client
        self.layout = layout
        self.selection = list(selection)
        self.fresh_coverage = fresh_coverage
        self.environment = {
            **os.environ,
            "REPO2REE_BUILD_REVISION": revision,
            "VITE_BUILD_REVISION": os.environ.get("VITE_BUILD_REVISION", revision),
            "E2E_ARCHIVE_DIR": str(layout.archives),
            "E2E_TEST_DIR": str(layout.directory),
        }
        self.coverage_dir = run_dir() / "python/coverage/data" / deployment.tier
        self.coverage_file = self.coverage_dir / ".coverage"
        self.control_state = deployment.state_root / "control" / layout.run_token
        descriptor, port_name = tempfile.mkstemp(prefix="repo2ree-e2e-port-")
        os.close(descriptor)
        self.port_file = Path(port_name)
        self.api_url = ""
        self.backend: subprocess.Popen[bytes] | None = None
        self.locations: list[subprocess.Popen[bytes]] = []
        self.running: Started | None = None
        self.logs: list[BinaryIO] = []
        self.stopped = False
        self.stop_lock = threading.Lock()
        self.client_status: int | None = None
        self.phases: dict[str, float] = {}

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        started = time.monotonic()
        try:
            yield
        finally:
            self.phases[name] = round(self.phases.get(name, 0.0) + time.monotonic() - started, 2)

    def log(self, path: Path) -> BinaryIO:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("wb")
        self.logs.append(handle)
        return handle

    def workbench_log(self, index: int) -> Path:
        suffix = "" if index == 1 else f"-{index}"
        return self.layout.logs / f"workbench-{self.deployment.tier}{suffix}.log"

    def prepare(self) -> None:
        if self.layout.telemetry is not None:
            self.layout.telemetry.mkdir(parents=True, exist_ok=True)
        for path in (self.layout.logs, self.coverage_dir, self.control_state):
            path.mkdir(parents=True, exist_ok=True)
        if self.fresh_coverage:
            for path in self.coverage_dir.glob(".coverage*"):
                path.unlink()
        for index in range(1, self.deployment.compute_locations + 1):
            self.workbench_log(index).unlink(missing_ok=True)

    def start_backend(self) -> None:
        log = self.layout.logs / f"backend-{self.deployment.tier}.log"
        print(f">> starting backend on an isolated port under coverage (log: {log})")
        environment = backend_environment(
            self.control_state, self.layout.run_token, self.coverage_file, self.layout.telemetry
        )
        backend = subprocess.Popen(
            ["coverage", "run", "--parallel-mode", "-m", "repo2ree_testbed.stack.serve_api", str(self.port_file)],
            cwd=ROOT,
            env={**self.environment, **environment},
            stdout=self.log(log),
            stderr=subprocess.STDOUT,
        )
        self.backend = backend

        def ready() -> bool:
            if backend.poll() is not None:
                tail = "\n".join(log.read_text(errors="replace").splitlines()[-50:])
                raise RuntimeError(f"backend process exited before readiness\n{tail}")
            port = self.port_file.read_text().strip() if self.port_file.is_file() else ""
            self.api_url = f"http://127.0.0.1:{port}" if port.isdigit() else ""
            return bool(self.api_url) and reachable(self.api_url + "/")

        wait_until("owned backend", ready)
        print(f">> backend ready at {self.api_url} (pid {backend.pid})")

    def start_locations(self) -> None:
        services = locations(self.deployment, self.api_url, self.control_state, self.layout.run_token)
        for index, service in enumerate(services, start=1):
            environment = dict(service.environment)
            if self.layout.telemetry is not None:
                environment["TRACE_FILE"] = str(self.layout.telemetry / f"location-{index}.ndjson")
            log = self.workbench_log(index)
            print(f">> starting {service.label} {index}/{len(services)} (log: {log})")
            command = ["uv", "run", "--package", service.package, "coverage", "run", "--parallel-mode"]
            self.locations.append(
                subprocess.Popen(
                    [*command, "-m", service.module],
                    cwd=ROOT,
                    env={**self.environment, **environment, "COVERAGE_FILE": str(self.coverage_file)},
                    stdout=self.log(log),
                    stderr=subprocess.STDOUT,
                )
            )
        key = "providers" if self.deployment.mode == "provider" else "workbenches"

        def ready() -> bool:
            if any(process.poll() is not None for process in self.locations):
                raise RuntimeError(f"{self.deployment.mode} process exited before readiness")
            return listed(f"{self.api_url}/api/v1/{key}", key) >= len(services)

        wait_until(f"{len(services)} {self.deployment.mode} service(s)", ready)

    def run_client(self) -> int:
        log = self.log(self.layout.client_log) if self.layout.client_log else None
        launch = Launch(self.layout.output, log, self.layout.test)
        running = self.client.start(self.api_url, self.environment, self.selection, launch)
        self.running = running
        infrastructure = [process for process in [self.backend, *self.locations] if process]
        while (status := running.poll()) is None:
            failed = next((process for process in infrastructure if process.poll() is not None), None)
            if failed:
                print(
                    f"stack process {failed.pid} exited during the client run (status {failed.returncode})",
                    file=sys.stderr,
                )
                terminate(running.process)
                running.poll()
                self.running = None
                return 1
            time.sleep(0.1)
        self.running = None
        return status

    def stop(self) -> None:
        with self.stop_lock:
            if self.stopped:
                return
            self.stopped = True
        terminate(self.running.process if self.running else None)
        if self.api_url:
            with self.phase("collect_live"):
                self.collect_live()
        with self.phase("shutdown"):
            for process in self.locations:
                terminate(process)
            terminate(self.backend)
        if self.api_url:
            with self.phase("export"):
                exported = self.collect_stopped()
            if exported:
                shutil.rmtree(self.control_state, ignore_errors=True)
        with self.phase("cleanup"):
            try:
                cleanup(self.layout.run_token, store=False, store_gc=None)
            except OSError as error:
                print(f"workbench cleanup failed: {error}", file=sys.stderr)
        self.port_file.unlink(missing_ok=True)
        for handle in self.logs:
            handle.close()

    def collect(self) -> list[str]:
        outcome = "passed" if self.client_status == 0 else "interrupted_or_failed"
        command = [sys.executable, "-m", "repo2ree_collect", str(self.layout.recording), "--suite", self.client.suite]
        command += ["--outcome", outcome]
        return [*command, "--test", self.layout.test] if self.layout.test else command

    def collect_live(self) -> None:
        command = [*self.collect(), "--control-plane", self.api_url, "--skip-owners"]
        for folder in (self.layout.archives, *self.client.archive_dirs(self.layout.output)):
            command += ["--archives-in", str(folder)]
        subprocess.run(command, cwd=ROOT, check=False)

    def collect_stopped(self) -> bool:
        command = [*self.collect(), "--journal-dir", str(self.control_state / "journal")]
        command += ["--runs-dir", str(self.control_state / "runs")]
        command += ["--allocations-file", str(self.control_state / "allocations.json")]
        telemetry = self.layout.telemetry
        for path in sorted(telemetry.glob("*.ndjson")) if telemetry is not None else []:
            command += ["--spans", str(path)]
        collected = subprocess.run(command, cwd=ROOT, check=False)
        status = "" if collected.returncode == 0 else " (incomplete: see the sources listed above)"
        print(f">> behaviour recording{status}: {self.layout.recording}")
        return collected.returncode == 0

    def coverage_report(self) -> None:
        environment = {**self.environment, "COVERAGE_FILE": str(self.coverage_file)}
        deployment = self.deployment
        print(
            f">> backend coverage ({deployment.tier} tier: server + {deployment.compute_locations} "
            f"{deployment.mode} compute-location process(es))"
        )
        subprocess.run(["coverage", "combine"], cwd=ROOT, env=environment, check=True)
        write_provenance(self.coverage_dir)
        subprocess.run(["coverage", "report"], cwd=ROOT, env=environment, check=True)
        render(CoverageRoot.current(), deployment.tier)

    def run_once(self) -> int:
        with self.phase("backend"):
            self.prepare()
            self.start_backend()
        with self.phase("locations"):
            self.start_locations()
        with self.phase("client"):
            self.client_status = self.run_client()
        print(">> stopping workbench service and backend (SIGTERM so coverage can flush)")
        self.stop()
        return self.client_status

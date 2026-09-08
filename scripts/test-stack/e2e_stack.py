#!/usr/bin/env python3
"""Run a measured source E2E stack and one client suite."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parents[2]


def capture(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def build_revision() -> str:
    return capture(str(ROOT / "scripts/build-revision.sh"))


def ws_url(http_url: str) -> str:
    return "ws:" + http_url.removeprefix("http:")


def json_count(url: str, key: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:  # noqa: S310 - owned local server
            return len(json.load(response).get(key, []))
    except (OSError, ValueError, urllib.error.URLError):
        return 0


@dataclass(frozen=True)
class Options:
    project: str
    script: Path | None
    tier: str
    record: Path | None
    compute_locations: int
    mode: str
    docker_mode: str
    state_root: Path
    exec_bundle: Path
    tools_bundle: Path


class E2EStack:
    def __init__(self, options: Options) -> None:
        self.options = options
        self.environment = os.environ.copy()
        revision = self.environment.get("REPO2REE_BUILD_REVISION") or build_revision()
        self.environment.setdefault("REPO2REE_BUILD_REVISION", revision)
        self.environment.setdefault("VITE_BUILD_REVISION", revision)
        self.run_token = f"e2e-{options.tier}-{uuid.uuid4().hex}"
        self.log_dir = ROOT / "test-artifacts/logs"
        self.coverage_dir = ROOT / "test-artifacts/coverage/python/data" / options.tier
        self.coverage_file = self.coverage_dir / ".coverage"
        self.control_state = options.state_root / "control" / self.run_token
        descriptor, port_name = tempfile.mkstemp(prefix="repo2ree-e2e-port-")
        os.close(descriptor)
        self.port_file = Path(port_name)
        self.api_url = ""
        self.backend: subprocess.Popen[bytes] | None = None
        self.locations: list[subprocess.Popen[bytes]] = []
        self.client: subprocess.Popen[bytes] | None = None
        self.logs: list[BinaryIO] = []
        self.stopped = False

    def workbench_log(self, index: int) -> Path:
        suffix = "" if index == 1 else f"-{index}"
        return self.log_dir / f"workbench-{self.options.tier}{suffix}.log"

    def prepare(self) -> None:
        for path in (
            self.log_dir,
            self.options.state_root / "workbenches",
            self.options.state_root / "providers",
            self.coverage_dir,
            self.control_state,
        ):
            path.mkdir(parents=True, exist_ok=True)
        for path in self.coverage_dir.glob(".coverage*"):
            path.unlink()
        for index in range(1, self.options.compute_locations + 1):
            self.workbench_log(index).unlink(missing_ok=True)

    def log_handle(self, path: Path) -> BinaryIO:
        handle = path.open("wb")
        self.logs.append(handle)
        return handle

    def start_backend(self) -> None:
        backend_log = self.log_dir / f"backend-{self.options.tier}.log"
        print(f">> starting backend on an isolated port under coverage (log: {backend_log})")
        environment = {
            **self.environment,
            "UPLOAD_STAGING_DIR": str(self.control_state / "upload-staging"),
            "ALLOCATION_STORE_FILE": str(self.control_state / "allocations.json"),
            "REE_INDEX_FILE": str(self.control_state / "ree-index.json"),
            "RUN_REGISTRY_DIR": str(self.control_state / "runs"),
            "EXTERNAL_WORKBENCH_TOKEN": self.run_token,
            "COVERAGE_FILE": str(self.coverage_file),
        }
        self.backend = subprocess.Popen(
            [
                "coverage",
                "run",
                "--parallel-mode",
                str(ROOT / "scripts/test-stack/serve-e2e-api.py"),
                str(self.port_file),
            ],
            cwd=ROOT,
            env=environment,
            stdout=self.log_handle(backend_log),
            stderr=subprocess.STDOUT,
        )
        self.wait_for_backend(backend_log)
        print(f">> backend ready at {self.api_url} (pid {self.backend.pid})")

    def wait_for_backend(self, log: Path) -> None:
        if self.backend is None:
            raise RuntimeError("backend was not started")
        for attempt in range(1, 31):
            if self.backend.poll() is not None:
                tail = "\n".join(log.read_text(errors="replace").splitlines()[-50:])
                raise RuntimeError(f"backend process exited before readiness\n{tail}")
            if self.port_file.is_file():
                value = self.port_file.read_text().strip()
                if value.isdigit():
                    self.api_url = f"http://127.0.0.1:{value}"
                    try:
                        with urllib.request.urlopen(self.api_url + "/", timeout=1):  # noqa: S310
                            return
                    except (OSError, urllib.error.URLError):
                        pass
            print(f"  waiting for owned backend... ({attempt}/30)")
            time.sleep(1)
        raise RuntimeError("owned backend did not become ready")

    def provider_network(self) -> tuple[str, str]:
        hostname = os.getenv("HOSTNAME", "")
        if not Path("/.dockerenv").is_file() or not hostname:
            return "host.docker.internal", ""
        inspect = subprocess.run(
            ["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", hostname],
            check=False,
            capture_output=True,
            text=True,
        )
        if inspect.returncode != 0:
            return "host.docker.internal", ""
        try:
            network = next(iter(json.loads(inspect.stdout)), "")
        except json.JSONDecodeError:
            network = ""
        return (hostname, network) if network else ("host.docker.internal", "")

    def start_locations(self) -> None:
        host, network = self.provider_network()
        for index in range(1, self.options.compute_locations + 1):
            if self.options.mode == "provider":
                base = self.options.state_root / "providers"
                state = base if index == 1 else Path(f"{base}-{index}")
                package = "repo2ree-provider-docker"
                module = "repo2ree_provider_docker"
                environment = {
                    "PROVIDER_API_WS_URL": ws_url(self.api_url) + "/provider/connect",
                    "PROVIDER_WORKBENCH_API_WS_URL": f"ws://{host}:{self.api_url.rsplit(':', 1)[1]}/workbench/connect",
                    "PROVIDER_WORKBENCH_DOCKER_NETWORK": network,
                    "PROVIDER_DOCKER_MODE": self.options.docker_mode,
                    "PROVIDER_LOCATION_ID": f"lab-{index}",
                    "PROVIDER_LOCATION_LABEL": f"Lab {index}",
                    "PROVIDER_STATE_DIR": str(state),
                    "REPO2REE_EXEC_BUNDLE": str(self.options.exec_bundle),
                    "REPO2REE_TOOLS_BUNDLE": str(self.options.tools_bundle),
                    "REPO2REE_RESOURCE_OWNER": self.run_token,
                }
                label = "Docker provider"
            else:
                base = self.options.state_root / "workbenches"
                state = base if index == 1 else Path(f"{base}-{index}")
                package = "repo2ree-workbench"
                module = "repo2ree_workbench"
                environment = {
                    "WORKBENCH_API_WS_URL": ws_url(self.api_url) + "/workbench/connect",
                    "WORKBENCH_MODE": "external",
                    "WORKBENCH_AUTH_TOKEN": self.run_token,
                    "WORKBENCH_LOCATION_ID": f"lab-{index}",
                    "WORKBENCH_ROOT": str(state / "root"),
                    "WORKBENCH_STATE_DIR": str(state),
                    "REPO2REE_EXEC_PATH": "repo2ree-exec",
                }
                label = "external workbench"
            log = self.workbench_log(index)
            print(f">> starting {label} {index}/{self.options.compute_locations} (log: {log})")
            process = subprocess.Popen(
                ["uv", "run", "--package", package, "coverage", "run", "--parallel-mode", "-m", module],
                cwd=ROOT,
                env={**self.environment, **environment, "COVERAGE_FILE": str(self.coverage_file)},
                stdout=self.log_handle(log),
                stderr=subprocess.STDOUT,
            )
            self.locations.append(process)
        key = "providers" if self.options.mode == "provider" else "workbenches"
        description = f"{self.options.compute_locations} {self.options.mode} service(s)"
        for attempt in range(1, 31):
            if json_count(f"{self.api_url}/api/v1/{key}", key) >= self.options.compute_locations:
                return
            if any(process.poll() is not None for process in self.locations):
                raise RuntimeError(f"{self.options.mode} process exited before readiness")
            print(f"  waiting for {description}... ({attempt}/30)")
            time.sleep(1)
        raise RuntimeError(f"{description} did not become ready")

    def start_client(self) -> tuple[subprocess.Popen[bytes], Path | None]:
        if self.options.script:
            print(f">> stack ready — running script={self.options.script}")
            if self.options.record:
                self.options.record.parent.mkdir(parents=True, exist_ok=True)
                descriptor, name = tempfile.mkstemp(prefix="repo2ree-record-status-")
                os.close(descriptor)
                status_file = Path(name)
                command = (
                    f"{shlex.quote(str(self.options.script))} --base-url {shlex.quote(self.api_url)}; "
                    f"printf '%s\\n' $? > {shlex.quote(str(status_file))}"
                )
                process = subprocess.Popen(
                    ["asciinema", "rec", "--overwrite", "-c", command, str(self.options.record)], cwd=ROOT
                )
                return process, status_file
            return subprocess.Popen([str(self.options.script), "--base-url", self.api_url], cwd=ROOT), None
        print(f">> stack ready — running playwright project={self.options.project}")
        environment = {
            **self.environment,
            "E2E_API_BASE_URL": self.api_url,
        }
        return (
            subprocess.Popen(
                [
                    "npm",
                    "exec",
                    "--",
                    "playwright",
                    "test",
                    "-c",
                    "playwright.config.ts",
                    f"--project={self.options.project}",
                ],
                cwd=ROOT / "gui",
                env=environment,
            ),
            None,
        )

    def wait_for_run(self) -> int:
        self.client, status_file = self.start_client()
        infrastructure = [process for process in [self.backend, *self.locations] if process]
        while True:
            client_status = self.client.poll()
            if client_status is not None:
                if status_file:
                    try:
                        client_status = int(status_file.read_text().strip())
                    except (OSError, ValueError):
                        client_status = 1
                    status_file.unlink(missing_ok=True)
                    print(f">> recorded terminal session: {self.options.record} (walkthrough exit {client_status})")
                self.client = None
                return client_status
            failed = next((process for process in infrastructure if process.poll() is not None), None)
            if failed:
                print(
                    f"stack process {failed.pid} exited during the client run (status {failed.returncode})",
                    file=sys.stderr,
                )
                self.terminate(self.client)
                self.client = None
                status_file.unlink(missing_ok=True) if status_file else None
                return 1
            time.sleep(0.1)

    @staticmethod
    def terminate(process: subprocess.Popen[bytes] | None) -> None:
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        self.terminate(self.client)
        for process in self.locations:
            self.terminate(process)
        self.terminate(self.backend)
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/test-stack/workbench_cleanup.py"), "--owner", self.run_token],
            cwd=ROOT,
            check=False,
        )
        self.port_file.unlink(missing_ok=True)
        for handle in self.logs:
            handle.close()

    def coverage_report(self) -> None:
        environment = {**self.environment, "COVERAGE_FILE": str(self.coverage_file)}
        print(
            f">> backend coverage ({self.options.tier} tier: server + {self.options.compute_locations} "
            f"{self.options.mode} compute-location process(es))"
        )
        subprocess.run(["coverage", "combine"], cwd=ROOT, env=environment, check=True)
        subprocess.run(["coverage", "report"], cwd=ROOT, env=environment, check=True)
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/coverage/python_coverage.py"), "render", self.options.tier],
            cwd=ROOT,
            env=environment,
            check=True,
        )

    def run(self) -> int:
        self.prepare()
        self.start_backend()
        self.start_locations()
        status = self.wait_for_run()
        print(">> stopping workbench service and backend (SIGTERM so coverage can flush)")
        self.stop()
        self.coverage_report()
        return status


def positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def options() -> Options:
    parser = argparse.ArgumentParser()
    runners = parser.add_mutually_exclusive_group(required=True)
    runners.add_argument("--project", default="")
    runners.add_argument("--script", type=Path)
    parser.add_argument("--tier", default="")
    parser.add_argument("--record", type=Path)
    parser.add_argument("--compute-locations", type=positive, default=1)
    parser.add_argument("--mode", choices=("provider", "external"), default="provider")
    parser.add_argument("--docker-mode", choices=("dind", "host-socket"), default="dind")
    parser.add_argument("--state-root", type=Path, default=ROOT / "test-artifacts/state")
    parser.add_argument("--exec-bundle", type=Path, default=ROOT / "dist/bundles/exec")
    parser.add_argument("--tools-bundle", type=Path, default=ROOT / "dist/bundles/tools")
    args = parser.parse_args()
    if args.project and args.tier:
        parser.error(f"--tier is implied by --project ({args.project}); drop it")
    if args.record and not args.script:
        parser.error("--record only applies to --script")
    tier = args.project or args.tier
    if args.script and not tier:
        parser.error("--script needs --tier <name> to say which tier it measures")
    if args.project:
        probe = subprocess.run(
            [
                "npm",
                "exec",
                "--",
                "playwright",
                "test",
                "-c",
                "playwright.config.ts",
                f"--project={args.project}",
                "--list",
            ],
            cwd=ROOT / "gui",
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode:
            print(probe.stdout + probe.stderr, file=sys.stderr, end="")
            parser.error(f"refusing to start the stack: playwright rejected --project={args.project}")
    return Options(
        project=args.project,
        script=args.script,
        tier=tier,
        record=args.record,
        compute_locations=args.compute_locations,
        mode=args.mode,
        docker_mode=args.docker_mode,
        state_root=args.state_root,
        exec_bundle=args.exec_bundle,
        tools_bundle=args.tools_bundle,
    )


def main() -> int:
    stack = E2EStack(options())

    def interrupted(_signal: int, _frame: object) -> None:
        stack.stop()
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        return stack.run()
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        stack.stop()


if __name__ == "__main__":
    raise SystemExit(main())

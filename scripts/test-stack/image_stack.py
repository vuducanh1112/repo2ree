#!/usr/bin/env python3
"""Manage the persistent image-backed demo and test stack."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATTACHMENT_FILE = ROOT / "test-artifacts/state/image-stack-caller-network"
PROVIDER_CONTAINER = "repo2ree-provider-docker"


def run(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
    quiet: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        env={**os.environ, **(env or {})},
        check=check,
        text=True,
        capture_output=capture,
        stdout=subprocess.DEVNULL if quiet and not capture else None,
        stderr=subprocess.DEVNULL if quiet and not capture else None,
    )


def capture(args: list[str], *, env: dict[str, str] | None = None, check: bool = False) -> str:
    return run(args, env=env, check=check, capture=True).stdout.strip()


def reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:  # noqa: S310 - caller chooses stack URL
            return int(response.status) < 400
    except (OSError, urllib.error.URLError):
        return False


@dataclass(frozen=True)
class Options:
    compute_locations: int = 1
    image_repository: str = ""
    image_tag: str = "local"
    gui_image: str = ""
    backend_image: str = ""
    provider_image: str = ""
    api_url: str = ""
    gui_url: str = ""


class ImageStack:
    def __init__(self, options: Options) -> None:
        self.options = options
        prefix = f"{options.image_repository}/" if options.image_repository else ""
        self.gui_image = (
            options.gui_image or os.getenv("STACK_GUI_IMAGE") or f"{prefix}repo2ree-gui:{options.image_tag}"
        )
        self.backend_image = (
            options.backend_image or os.getenv("STACK_BACKEND_IMAGE") or f"{prefix}repo2ree-backend:{options.image_tag}"
        )
        self.provider_image = (
            options.provider_image
            or os.getenv("STACK_PROVIDER_IMAGE")
            or f"{prefix}repo2ree-provider-docker:{options.image_tag}"
        )
        self.api_url = options.api_url
        self.gui_url = options.gui_url

    def compose(self, *args: str, check: bool = True, capture_output: bool = False) -> str:
        environment = {"REPO2REE_GUI_IMAGE": self.gui_image, "REPO2REE_BACKEND_IMAGE": self.backend_image}
        if capture_output:
            return capture(["docker", "compose", *args], env=environment, check=check)
        run(["docker", "compose", *args], env=environment, check=check)
        return ""

    @staticmethod
    def provider_name(index: int) -> str:
        return PROVIDER_CONTAINER if index == 1 else f"{PROVIDER_CONTAINER}-{index}"

    def provider_compose(
        self,
        name: str,
        *args: str,
        environment: dict[str, str] | None = None,
        check: bool = True,
        quiet: bool = False,
    ) -> None:
        run(
            ["docker", "compose", "-p", name, "-f", "docker-compose.workbench.yml", *args],
            env={
                "REPO2REE_PROVIDER_IMAGE": self.provider_image,
                "REPO2REE_PROVIDER_CONTAINER": name,
                "REPO2REE_PROVIDER_STATE_VOLUME": f"{name}-state",
                **(environment or {}),
            },
            check=check,
            quiet=quiet,
        )

    def control_plane_network(self) -> str:
        backend = self.compose("ps", "-q", "backend", check=False, capture_output=True).splitlines()
        if not backend:
            return ""
        output = capture(["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", backend[0]], check=False)
        if not output:
            return ""
        try:
            return next(iter(json.loads(output)), "")
        except json.JSONDecodeError:
            return ""

    def resolve_urls(self) -> None:
        if (
            run(["getent", "hosts", "backend"], check=False, quiet=True).returncode == 0
            and run(["getent", "hosts", "gui"], check=False, quiet=True).returncode == 0
        ):
            default_api = "http://backend:8000"
            default_gui = "http://gui:3000"
        elif Path("/.dockerenv").is_file():
            if run(["getent", "hosts", "host.docker.internal"], check=False, quiet=True).returncode == 0:
                host = "host.docker.internal"
            else:
                hostname = os.getenv("HOSTNAME", "")
                networks = capture(
                    ["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", hostname], check=False
                )
                try:
                    values = json.loads(networks).values() if networks else []
                    host = next((value.get("Gateway", "") for value in values if value.get("Gateway")), "")
                except json.JSONDecodeError:
                    host = ""
            host = host or "localhost"
            default_api = f"http://{host}:8000"
            default_gui = f"http://{host}:3000"
        else:
            default_api = "http://localhost:8000"
            default_gui = "http://localhost:3000"
        self.api_url = self.options.api_url or default_api
        self.gui_url = self.options.gui_url or default_gui

    def attach_caller(self) -> None:
        hostname = os.getenv("HOSTNAME", "")
        if not Path("/.dockerenv").is_file() or not hostname:
            return
        if run(["docker", "inspect", hostname], check=False, quiet=True).returncode != 0:
            return
        network = self.control_plane_network()
        if not network:
            return
        output = capture(["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", hostname])
        try:
            if network in json.loads(output):
                return
        except json.JSONDecodeError:
            return
        run(["docker", "network", "connect", network, hostname])
        ATTACHMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        ATTACHMENT_FILE.write_text(f"{hostname} {network}\n")
        print(f">> attached calling container to {network}", file=sys.stderr)

    @staticmethod
    def detach_caller() -> None:
        if not ATTACHMENT_FILE.is_file():
            return
        fields = ATTACHMENT_FILE.read_text().split()
        if len(fields) == 2:
            run(["docker", "network", "disconnect", fields[1], fields[0]], check=False, quiet=True)
        ATTACHMENT_FILE.unlink(missing_ok=True)

    @staticmethod
    def wait_until(description: str, probe: Callable[[], bool]) -> None:
        for attempt in range(1, 31):
            if probe():
                return
            print(f"  waiting for {description}... ({attempt}/30)")
            time.sleep(1)
        raise RuntimeError(f"{description} did not become ready")

    def provider_count(self) -> int:
        if not self.api_url:
            raise RuntimeError("API URL has not been resolved")
        try:
            with urllib.request.urlopen(  # noqa: S310 - URL is selected by the stack caller
                f"{self.api_url}/api/v1/providers", timeout=1
            ) as response:
                return len(json.load(response).get("providers", []))
        except (OSError, ValueError, urllib.error.URLError):
            return 0

    def up(self) -> None:
        self.resolve_urls()
        for image in (self.gui_image, self.backend_image, self.provider_image):
            if "/" in image:
                print(f">> pulling {image}")
                run(["docker", "pull", image])
            elif run(["docker", "image", "inspect", image], check=False, quiet=True).returncode != 0:
                raise RuntimeError(f"{image} not found — build the local images first: just images")
        print(f">> starting compose control plane ({self.gui_image}, {self.backend_image})")
        self.compose("up", "-d", "backend", "gui")
        count = self.options.compute_locations
        print(f">> starting {count} Docker provider service(s) ({self.provider_image})")
        network = self.control_plane_network()
        for index in range(1, count + 1):
            name = self.provider_name(index)
            environment: dict[str, str] = {}
            if network:
                environment = {
                    "PROVIDER_API_WS_URL": "ws://backend:8000/provider/connect",
                    "PROVIDER_WORKBENCH_API_WS_URL": "ws://backend:8000/workbench/connect",
                    "PROVIDER_WORKBENCH_DOCKER_NETWORK": network,
                }
            self.provider_compose(name, "up", "-d", environment=environment, quiet=True)
            if network:
                run(["docker", "network", "connect", network, name], check=False, quiet=True)
        self.attach_caller()
        self.resolve_urls()
        print(f">> probing stack endpoints — API {self.api_url}, GUI {self.gui_url}")
        self.wait_until(f"backend at {self.api_url}", lambda: reachable(self.api_url))
        self.wait_until(f"{count} provider service(s)", lambda: self.provider_count() >= count)
        self.wait_until(f"gui at {self.gui_url}", lambda: reachable(self.gui_url))
        print(f">> stack up — GUI at {self.gui_url}")

    def down(self, volumes: bool = False) -> None:
        self.detach_caller()
        args = ("down", "-v") if volumes else ("down",)
        print(">> stopping workbench service stack(s)")
        names = capture(["docker", "ps", "-a", "--format", "{{.Names}}"], check=False).splitlines()
        pattern = re.compile(rf"{re.escape(PROVIDER_CONTAINER)}(?:-[0-9]+)?")
        for name in names:
            if pattern.fullmatch(name):
                self.provider_compose(name, *args, check=False, quiet=True)
        if volumes:
            run([sys.executable, str(ROOT / "scripts/test-stack/workbench_cleanup.py")])
        print(">> stopping compose control plane")
        self.compose(*args)

    def check(self) -> None:
        self.attach_caller()
        self.resolve_urls()
        if not reachable(self.api_url):
            raise RuntimeError(f"backend not reachable at {self.api_url} — start the image stack first (just stack-up)")
        if self.provider_count() < 1:
            raise RuntimeError("no provider service connected — start the provider container (just stack-up)")
        if not reachable(self.gui_url):
            raise RuntimeError(f"GUI not reachable at {self.gui_url} — start the image stack first (just stack-up)")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    commands = result.add_subparsers(dest="command", required=True)
    up = commands.add_parser("up")
    up.add_argument("--compute-locations", type=int, default=1)
    up.add_argument("--image-repository", default="")
    up.add_argument("--image-tag", default="local")
    up.add_argument("--gui-image", default="")
    up.add_argument("--backend-image", default="")
    up.add_argument("--provider-image", default="")
    down = commands.add_parser("down")
    down.add_argument("--volumes", action="store_true")
    for name in ("check", "gui-url", "api-url"):
        command = commands.add_parser(name)
        command.add_argument("--api-url", default="")
        command.add_argument("--gui-url", default="")
    return result


def main() -> int:
    args = parser().parse_args()
    if getattr(args, "compute_locations", 1) < 1:
        print("compute locations must be a positive integer", file=sys.stderr)
        return 2
    options = Options(
        compute_locations=getattr(args, "compute_locations", 1),
        image_repository=getattr(args, "image_repository", ""),
        image_tag=getattr(args, "image_tag", "local"),
        gui_image=getattr(args, "gui_image", ""),
        backend_image=getattr(args, "backend_image", ""),
        provider_image=getattr(args, "provider_image", ""),
        api_url=getattr(args, "api_url", ""),
        gui_url=getattr(args, "gui_url", ""),
    )
    stack = ImageStack(options)
    try:
        if args.command == "up":
            stack.up()
        elif args.command == "down":
            stack.down(args.volumes)
        elif args.command == "check":
            stack.check()
        else:
            stack.attach_caller()
            stack.resolve_urls()
            print(stack.gui_url if args.command == "gui-url" else stack.api_url)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

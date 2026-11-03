"""The persistent image-backed stack: the compose control plane, its store's workbench, and more stores.

The main compose file runs the backend, the GUI, store-init and the first store's workbench. Each further
compute location is a workbench of its own (docker-compose.workbench.yml) serving a store registered, and
its token minted, with the backend's store_admin. Every store keeps its REEs in a host directory mounted at
the same path in its workbench, so the job containers the host engine starts see them where it does.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.stack.docker import first_network, networks, own_container
from repo2ree_testbed.stack.process import capture, fetch_json, reachable, run, wait_until
from repo2ree_testbed.stack.store_images import STORE_IMAGES
from repo2ree_testbed.stack.workbench_cleanup import cleanup

ATTACHMENT_FILE = ROOT / "test-artifacts/state/image-stack-caller-network"
WORKBENCH_CONTAINER = "repo2ree-workbench"
# Where each store keeps its REEs on the engine's host, mounted at the same path in its workbench.
STORE_ROOT = "/var/lib/repo2ree/image-stack"


@dataclass(frozen=True)
class Images:
    gui: str
    backend: str
    workbench: str

    @classmethod
    def tagged(cls, repository: str = "", tag: str = "local") -> Images:
        prefix = f"{repository}/" if repository else ""
        return cls(
            os.getenv("STACK_GUI_IMAGE") or f"{prefix}repo2ree-gui:{tag}",
            os.getenv("STACK_BACKEND_IMAGE") or f"{prefix}repo2ree-backend:{tag}",
            os.getenv("STACK_WORKBENCH_IMAGE") or f"{prefix}repo2ree-workbench:{tag}",
        )


@dataclass(frozen=True)
class Urls:
    api: str
    gui: str


class ImageStack:
    def __init__(self, images: Images, compute_locations: int = 1) -> None:
        self.images = images
        self.compute_locations = compute_locations

    def compose(self, *args: str, check: bool = True) -> None:
        environment = {
            "REPO2REE_GUI_IMAGE": self.images.gui,
            "REPO2REE_BACKEND_IMAGE": self.images.backend,
            "REPO2REE_WORKBENCH_IMAGE": self.images.workbench,
            **self.store_environment(1),
        }
        run(["docker", "compose", *args], env=environment, check=check)

    @staticmethod
    def store_environment(index: int) -> dict[str, str]:
        return {
            "REPO2REE_STORE_ID": f"lab-{index}",
            "REPO2REE_STORE_DIR": f"{STORE_ROOT}/lab-{index}",
            "REPO2REE_STORE_IMAGE": ",".join(STORE_IMAGES),
        }

    @staticmethod
    def workbench_name(index: int) -> str:
        return f"{WORKBENCH_CONTAINER}-{index}"

    def workbench_compose(self, name: str, *args: str, environment: dict[str, str], check: bool = True) -> None:
        run(
            ["docker", "compose", "-p", name, "-f", "docker-compose.workbench.yml", *args],
            env={
                "REPO2REE_WORKBENCH_IMAGE": self.images.workbench,
                "REPO2REE_WORKBENCH_CONTAINER": name,
                "REPO2REE_WORKBENCH_STATE_VOLUME": f"{name}-state",
                # The file requires a token; one that stops or removes the stack never presents it.
                "WORKBENCH_AUTH_TOKEN": "unused",
                **environment,
            },
            check=check,
            quiet=True,
        )

    def mint_token(self, store_id: str) -> str:
        """Register ``store_id`` with the backend unless it is, and a new token for its workbench."""
        admin = ["docker", "compose", "exec", "-T", "backend", "python", "-m", "repo2ree_api.store_admin"]
        environment = {"REPO2REE_GUI_IMAGE": self.images.gui, "REPO2REE_BACKEND_IMAGE": self.images.backend}
        run([*admin, "add", store_id], env=environment, check=False, quiet=True)
        return capture([*admin, "token", store_id], env=environment).strip().splitlines()[-1]

    def control_plane_network(self) -> str:
        environment = {"REPO2REE_GUI_IMAGE": self.images.gui, "REPO2REE_BACKEND_IMAGE": self.images.backend}
        backend = capture(["docker", "compose", "ps", "-q", "backend"], env=environment).splitlines()
        return first_network(backend[0]) if backend else ""

    @staticmethod
    def resolve(overrides: Urls | None = None) -> Urls:
        def resolves(host: str) -> bool:
            return run(["getent", "hosts", host], check=False, quiet=True).returncode == 0

        if resolves("backend") and resolves("gui"):
            found = Urls("http://backend:8000", "http://gui:3000")
        else:
            host = "localhost"
            if Path("/.dockerenv").is_file():
                container = own_container() or ""
                gateways = (network.Gateway for network in networks(container).values() if network.Gateway)
                host = "host.docker.internal" if resolves("host.docker.internal") else next(gateways, "localhost")
            found = Urls(f"http://{host}:8000", f"http://{host}:3000")
        if overrides is None:
            return found
        return Urls(overrides.api or found.api, overrides.gui or found.gui)

    def attach_caller(self) -> None:
        container = own_container()
        attached = networks(container) if container else {}
        network = self.control_plane_network() if attached else ""
        if not container or not network or network in attached:
            return
        run(["docker", "network", "connect", network, container])
        ATTACHMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        ATTACHMENT_FILE.write_text(f"{container} {network}\n")
        print(f">> attached calling container to {network}", file=sys.stderr)

    @staticmethod
    def detach_caller() -> None:
        if not ATTACHMENT_FILE.is_file():
            return
        fields = ATTACHMENT_FILE.read_text().split()
        if len(fields) == 2:
            run(["docker", "network", "disconnect", fields[1], fields[0]], check=False, quiet=True)
        ATTACHMENT_FILE.unlink(missing_ok=True)

    def up(self) -> Urls:
        for image in (self.images.gui, self.images.backend, self.images.workbench):
            if "/" in image:
                print(f">> pulling {image}")
                run(["docker", "pull", image])
            elif run(["docker", "image", "inspect", image], check=False, quiet=True).returncode != 0:
                raise RuntimeError(f"{image} not found — build the local images first: just build-images")
        print(f">> starting compose control plane and store lab-1 ({self.images.gui}, {self.images.backend})")
        self.compose("up", "-d", "backend", "gui", "store-init", "workbench")
        network = self.control_plane_network()
        count = self.compute_locations
        for index in range(2, count + 1):
            name = self.workbench_name(index)
            print(f">> starting store lab-{index}'s workbench ({self.images.workbench})")
            environment = {
                **self.store_environment(index),
                "REPO2REE_API_WS_URL": "ws://backend:8000/workbench/connect",
                "WORKBENCH_AUTH_TOKEN": self.mint_token(f"lab-{index}"),
            }
            self.workbench_compose(name, "up", "-d", environment=environment)
            if network:
                run(["docker", "network", "connect", network, name], check=False, quiet=True)
        self.attach_caller()
        urls = self.resolve()
        print(f">> probing stack endpoints — API {urls.api}, GUI {urls.gui}")
        wait_until(f"backend at {urls.api}", lambda: reachable(urls.api))
        wait_until(f"{count} store(s) served", lambda: served_stores(urls.api) >= count)
        wait_until(f"gui at {urls.gui}", lambda: reachable(urls.gui))
        print(f">> stack up — GUI at {urls.gui}")
        return urls

    def down(self, *, volumes: bool = False) -> None:
        self.detach_caller()
        args = ("down", "-v") if volumes else ("down",)
        print(">> stopping store workbench stack(s)")
        pattern = re.compile(rf"{re.escape(WORKBENCH_CONTAINER)}-[0-9]+")
        for name in capture(["docker", "ps", "-a", "--format", "{{.Names}}"]).splitlines():
            if pattern.fullmatch(name):
                self.workbench_compose(name, *args, environment={}, check=False)
        print(">> stopping compose control plane")
        self.compose(*args)
        if volumes:
            cleanup(None)
            # The stores' REEs are host directories, not volumes: the engine's host removes them.
            remove = ["docker", "run", "--rm", "-v", f"{STORE_ROOT}:{STORE_ROOT}", self.images.workbench]
            run([*remove, "rm", "-rf", STORE_ROOT], check=False, quiet=True)

    def check(self, overrides: Urls | None = None) -> Urls:
        self.attach_caller()
        urls = self.resolve(overrides)
        if not reachable(urls.api):
            raise RuntimeError(f"backend not reachable at {urls.api} — start the image stack first (just stack-up)")
        if served_stores(urls.api) < 1:
            raise RuntimeError("no store's workbench connected — start the image stack first (just stack-up)")
        if not reachable(urls.gui):
            raise RuntimeError(f"GUI not reachable at {urls.gui} — start the image stack first (just stack-up)")
        return urls


def served_stores(api: str) -> int:
    """How many stores a workbench serves now."""
    listed = fetch_json(f"{api}/api/v1/stores")
    stores = listed.get("stores") if isinstance(listed, dict) else None
    if not isinstance(stores, list):
        return 0
    return sum(1 for store in stores if isinstance(store, dict) and store.get("connected"))


@dataclass(frozen=True)
class Up:
    images: Images
    compute_locations: int


@dataclass(frozen=True)
class Down:
    volumes: bool


@dataclass(frozen=True)
class Probe:
    command: Literal["check", "gui-url", "api-url"]
    urls: Urls


type Command = Up | Down | Probe


def parse(argv: list[str] | None = None) -> Command:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed images")
    commands = parser.add_subparsers(dest="command", required=True)
    up = commands.add_parser("up")
    up.add_argument("--compute-locations", type=int, default=1)
    up.add_argument("--image-repository", default="")
    up.add_argument("--image-tag", default="local")
    up.add_argument("--gui-image", default="")
    up.add_argument("--backend-image", default="")
    up.add_argument("--workbench-image", default="")
    commands.add_parser("down").add_argument("--volumes", action="store_true")
    for name in ("check", "gui-url", "api-url"):
        probe = commands.add_parser(name)
        probe.add_argument("--api-url", default="")
        probe.add_argument("--gui-url", default="")
    args = parser.parse_args(argv)
    if args.command == "up":
        if args.compute_locations < 1:
            parser.error("compute locations must be a positive integer")
        tagged = Images.tagged(args.image_repository, args.image_tag)
        images = Images(
            args.gui_image or tagged.gui, args.backend_image or tagged.backend, args.workbench_image or tagged.workbench
        )
        return Up(images, args.compute_locations)
    if args.command == "down":
        return Down(args.volumes)
    return Probe(args.command, Urls(args.api_url, args.gui_url))


def main() -> int:
    command = parse()
    try:
        match command:
            case Up(images, count):
                ImageStack(images, count).up()
            case Down(volumes):
                ImageStack(Images.tagged()).down(volumes=volumes)
            case Probe("check", urls):
                ImageStack(Images.tagged()).check(urls)
            case Probe(kind, urls):
                stack = ImageStack(Images.tagged())
                stack.attach_caller()
                resolved = stack.resolve(urls)
                print(resolved.gui if kind == "gui-url" else resolved.api)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

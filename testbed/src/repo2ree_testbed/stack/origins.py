"""Origins a stack serves itself: the fixture project by git and as a tarball, instead of a public host.

The suites that fetch a source from an origin URL (and the reviews that fetch it again)
used to reach a repository on GitHub, so they needed the internet and tested whatever that
repository held that day. Each stack now serves ``examples/origins/ree-e2e-fixture`` itself:

- by git, over git's smart HTTP protocol (``origin_server``, through ``git http-backend``),
  which the product's shallow, revision-pinned fetch needs and an http(s) URL reaches;
- as a ``.tar.gz``, from the same server.

The repository is built with a fixed author, committer and date, and the tarball with
fixed metadata, so every run serves the same commit and the same bytes. Benches reach
both the way they reach the API (``host`` below).
"""

from __future__ import annotations

import gzip
import io
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path

from repo2ree_testbed.artifacts import ROOT

FIXTURE = ROOT / "examples/origins/ree-e2e-fixture"
REPOSITORY = "ree-e2e-fixture.git"
TARBALL = "ree-e2e-fixture.tar.gz"
# What the repository is committed as, so its commit id never changes between runs.
_IDENTITY = {
    "GIT_AUTHOR_NAME": "repo2ree e2e",
    "GIT_AUTHOR_EMAIL": "e2e@repo2ree.invalid",
    "GIT_COMMITTER_NAME": "repo2ree e2e",
    "GIT_COMMITTER_EMAIL": "e2e@repo2ree.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


@dataclass(frozen=True)
class Served:
    git_url: str
    tarball_url: str

    def environment(self) -> dict[str, str]:
        return {"E2E_GIT_ORIGIN_URL": self.git_url, "E2E_TARBALL_ORIGIN_URL": self.tarball_url}


def _git(*args: str, cwd: Path) -> None:
    # No user or system configuration: a signing or hook setting would change the commit.
    environment = {"PATH": os.environ.get("PATH", ""), "HOME": str(cwd), "GIT_CONFIG_NOSYSTEM": "1", **_IDENTITY}
    subprocess.run(["git", *args], cwd=cwd, env=environment, check=True, capture_output=True)


def build_repository(served: Path) -> Path:
    """A bare repository of the fixture, one commit on ``main``, fetchable by commit id."""
    work = served / "work"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(FIXTURE, work)
    _git("init", "-q", "-b", "main", cwd=work)
    _git("add", "-A", cwd=work)
    _git("commit", "-q", "-m", "The e2e origin fixture", cwd=work)
    bare = served / REPOSITORY
    shutil.rmtree(bare, ignore_errors=True)
    _git("clone", "-q", "--bare", str(work), str(bare), cwd=served)
    # The product fetches a pinned revision by its id, as public hosts allow.
    _git("config", "uploadpack.allowReachableSHA1InWant", "true", cwd=bare)
    _git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=bare)
    shutil.rmtree(work)
    return bare


def build_tarball(served: Path) -> Path:
    """The fixture as ``ree-e2e-fixture/…`` in a tarball whose bytes depend on its files alone."""
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for path in sorted(FIXTURE.rglob("*")):
            info = tar.gettarinfo(str(path), arcname=f"ree-e2e-fixture/{path.relative_to(FIXTURE)}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 1767225600  # 2026-01-01
            info.mode = 0o755 if path.is_dir() else 0o644
            tar.addfile(info, io.BytesIO(path.read_bytes()) if path.is_file() else None)
    target = served / TARBALL
    with target.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
        compressed.write(archive.getvalue())
    return target


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("0.0.0.0", 0))  # noqa: S104 - test stack; reachable from workbench containers by design
        return int(probe.getsockname()[1])


class Origins:
    """The two origin servers of one stack: started with it, stopped with it."""

    def __init__(self, directory: Path, host: str) -> None:
        self.directory = directory
        self.host = host
        self.processes: list[subprocess.Popen[bytes]] = []

    def start(self, log: Path) -> Served:
        self.directory.mkdir(parents=True, exist_ok=True)
        build_repository(self.directory)
        build_tarball(self.directory)
        port = free_port()
        with log.open("ab") as output:
            self.processes.append(
                subprocess.Popen(
                    [sys.executable, "-m", "repo2ree_testbed.stack.origin_server", str(self.directory), str(port)],
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            )
        _wait_listening(port)
        return Served(
            git_url=f"http://{self.host}:{port}/{REPOSITORY}",
            tarball_url=f"http://{self.host}:{port}/{TARBALL}",
        )

    def stop(self) -> None:
        for process in self.processes:
            process.terminate()
        for process in self.processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        self.processes = []


def _wait_listening(port: int, attempts: int = 50) -> None:
    for _ in range(attempts):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"an origin server did not start listening on port {port}")

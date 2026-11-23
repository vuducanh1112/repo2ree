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
UPSTREAM = "upstream"
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
    upstream_url: str
    upstream_directory: Path

    def environment(self) -> dict[str, str]:
        return {
            "E2E_GIT_ORIGIN_URL": self.git_url,
            "E2E_TARBALL_ORIGIN_URL": self.tarball_url,
            "E2E_UPSTREAM_URL": self.upstream_url,
            "E2E_UPSTREAM_DIR": str(self.upstream_directory),
        }


def _git(*args: str, cwd: Path) -> None:
    environment = {"PATH": os.environ.get("PATH", ""), "HOME": str(cwd), "GIT_CONFIG_NOSYSTEM": "1", **_IDENTITY}
    subprocess.run(["git", *args], cwd=cwd, env=environment, check=True, capture_output=True)


def build_repository(served: Path) -> Path:
    work = served / "work"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(FIXTURE, work)
    _git("init", "-q", "-b", "main", cwd=work)
    _git("add", "-A", cwd=work)
    _git("commit", "-q", "-m", "The e2e origin fixture", cwd=work)
    bare = served / REPOSITORY
    shutil.rmtree(bare, ignore_errors=True)
    _git("clone", "-q", "--bare", str(work), str(bare), cwd=served)
    _git("config", "uploadpack.allowReachableSHA1InWant", "true", cwd=bare)
    _git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=bare)
    shutil.rmtree(work)
    return bare


def build_tarball(served: Path) -> Path:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for path in sorted(FIXTURE.rglob("*")):
            info = tar.gettarinfo(str(path), arcname=f"ree-e2e-fixture/{path.relative_to(FIXTURE)}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 1767225600
            info.mode = 0o755 if path.is_dir() else 0o644
            tar.addfile(info, io.BytesIO(path.read_bytes()) if path.is_file() else None)
    target = served / TARBALL
    with target.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
        compressed.write(archive.getvalue())
    return target


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("0.0.0.0", 0))  # noqa: S104
        return int(probe.getsockname()[1])


class Origins:
    def __init__(self, directory: Path, host: str) -> None:
        self.directory = directory
        self.host = host
        self.processes: list[subprocess.Popen[bytes]] = []

    def start(self, log: Path) -> Served:
        self.directory.mkdir(parents=True, exist_ok=True)
        build_repository(self.directory)
        build_tarball(self.directory)
        upstream = self.directory / UPSTREAM
        shutil.rmtree(upstream, ignore_errors=True)
        upstream.mkdir()
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
            upstream_url=f"http://{self.host}:{port}/{UPSTREAM}",
            upstream_directory=upstream,
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

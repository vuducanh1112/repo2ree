"""``python -m repo2ree_testbed machine``: run the gate or a tier on a machine, here or over SSH.

A machine is where the stacks run. ``local`` is this checkout; any other is an SSH
machine named in the machines file (``$REPO2REE_MACHINES``, by default the untracked
``.config/machines.toml`` of this checkout), since hosts and paths are a developer's own:

    [machines.vm]
    host = "vm"          # an ssh destination: an alias, or user@host
    path = "repo2ree"    # the clone on the machine, relative to its home or absolute
    jobs = 6             # stacks side by side per tier
    # shell = [...]      what every command runs inside; by default the clone's .envrc, via direnv
    # fetch = "slim"     # or "full": "slim" leaves runtime tarballs and archives behind
    # container = "repo2ree-dev"                  the container everything there runs in
    # dockerfile = "docker/dev/nix.Dockerfile"    the dev image it runs

A remote machine runs nothing on itself: it needs only a Docker Engine its SSH user
may use. `prepare` builds the dev image from HEAD there and starts it as the
container, on the machine's Docker, with the clone in a volume. A run then pushes
HEAD into the container, checks it out clean, runs the recipe in its dev shell, and
sends back every per-test run the recipe reported; the gate also sends back its
receipt, which binds a tree rather than a machine, so it holds here as it did there.
Only a commit can be shipped, so the repository needs to be committed. A run refuses
a container that is not running, or that was built from other image inputs (the
Dockerfile and what it copies) than HEAD's: `prepare` again. `remove` cleans up
what runs left on that Docker and removes the container, its volume, network, and images.

On a remote machine the recipe runs as a job detached from SSH: its output goes to a
log in the clone's test-artifacts, which the run follows. A dropped connection only
stops the following; the run reconnects for a while, and after that the same command
again, at the same commit, picks the job back up, or its results once it ended. One
job runs at a time: anything else that would touch the clone or the container refuses
while one does. Ctrl-C cancels the job; `cancel` does so from anywhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.machines import NIX, MachineConfig, load_machines, machines_file
from repo2ree_testbed.stack.process import capture

RUN_LINE = ">> per-test run: "
# Git on the machine comes from Nix, as everything else does: before the clone exists
# there is no dev shell to take it from.
GIT = shlex.join([*NIX, "shell", "nixpkgs#git", "--command", "git"])
# What a push runs on the machine. Git appends the repository's path, which a login
# shell receives as $0.
RECEIVE_PACK = "bash -lc " + shlex.quote(
    shlex.join([*NIX, "shell", "nixpkgs#git", "--command", "git-receive-pack"]) + ' "$0"'
)
RECEIPT = ".receipts/assurance-gate.json"
# The dev image's user, and the home a container machine's relative paths start from.
CONTAINER_USER = "nixuser"
CONTAINER_HOME = "/home/nixuser"
DOCKER_SOCKET = "/var/run/docker.sock"
# What ssh exits with when it cannot connect or log in, as opposed to the remote command failing.
SSH_FAILED = 255
# What the container check exits with, beyond success.
NOT_RUNNING = 3
OTHER_SOURCE = 4
# On the container: a hash of the image it runs, and of the image inputs it was built from.
IMAGE_LABEL = "repo2ree.dev-image"
SOURCE_LABEL = "repo2ree.dev-source"
IMAGE_FINGERPRINT = "{{json .RootFS.Layers}}{{json .Config}}"
CONTAINER_STATE = (
    f'{{{{.State.Running}}}} {{{{index .Config.Labels "{IMAGE_LABEL}"}}}} {{{{index .Config.Labels "{SOURCE_LABEL}"}}}}'
)
# Where a remote job keeps its command, process, log, and exit code, relative to the clone.
JOB = "test-artifacts/machine-job"
# The last line a job's follow prints, after the job's log: how it ended.
JOB_EXITED = ">> machine job exited: "
JOB_LOST = ">> machine job lost"
# What the job check exits with: the job asked for is there, running or not yet fetched;
# another one runs; another one ended but was never fetched; or one died without an exit code.
THIS_JOB = 10
OTHER_RUNNING = 11
OTHER_UNFETCHED = 12
LOST_JOB = 13
# How long a run keeps reconnecting to its job before it leaves the job to a rerun.
RECONNECT_SECONDS = 30 * 60
INTERRUPTED = 130
# A dropped connection shows within a minute instead of whenever TCP gives up.
KEEPALIVE = ("-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4")
# The machines' host keys, kept beside the machines file by tools/ssh/setup-vm.sh, so they outlive a
# rebuilt dev container; a machine whose key is in neither file is refused, not asked about.
KNOWN_HOSTS = ROOT / ".config" / "known_hosts"
SSH_OPTIONS = (
    *KEEPALIVE,
    "-o",
    f"UserKnownHostsFile={KNOWN_HOSTS} ~/.ssh/known_hosts",
    "-o",
    "StrictHostKeyChecking=yes",
)
# The networks a container is on, each followed by a space.
CONTAINER_NETWORKS = "{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}"
# What a slim fetch leaves on the machine: the bulk of a run, and nothing a verdict or a page reads.
SLIM_EXCLUDES = ("*.tar", "*.tar.gz", "*.tgz", "*/artifacts/archives")


class Runner(Protocol):
    def call(self, argv: Sequence[str]) -> int: ...

    def stream(self, argv: Sequence[str]) -> tuple[int, list[str]]:
        """Run ``argv`` showing its output as it comes; its exit code, and every complete line it printed."""
        ...

    def pipe(self, producer: Sequence[str], consumer: Sequence[str]) -> int: ...


class Processes:
    def call(self, argv: Sequence[str]) -> int:
        return subprocess.run(list(argv), cwd=ROOT, check=False).returncode

    def stream(self, argv: Sequence[str]) -> tuple[int, list[str]]:
        printed: list[str] = []
        with subprocess.Popen(
            list(argv), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        ) as proc:
            for line in proc.stdout or ():
                sys.stdout.write(line)
                # A line cut off by a dropped connection is not counted: following again shows it whole.
                if line.endswith("\n"):
                    printed.append(line.removesuffix("\n"))
        return proc.returncode, printed

    def pipe(self, producer: Sequence[str], consumer: Sequence[str]) -> int:
        with (
            subprocess.Popen(list(producer), cwd=ROOT, stdout=subprocess.PIPE) as source,
            subprocess.Popen(list(consumer), cwd=ROOT, stdin=source.stdout) as sink,
        ):
            # Only the consumer reads it now, so a consumer that stops early stops the producer too.
            if source.stdout is not None:
                source.stdout.close()
            received = sink.wait()
        return source.returncode or received


@dataclass
class Machine:
    """One machine, reached the way its kind is reached; the same verbs either way."""

    name: str
    config: MachineConfig
    runner: Runner = field(default_factory=Processes)
    sleep: Callable[[float], None] = time.sleep

    @property
    def remote(self) -> bool:
        return self.config.host is not None

    def provision(self, revision: str) -> None:
        """Build the dev image from ``revision`` on the machine, and run it as the container if it is new."""
        if not self.remote:
            return
        if self._check_container() == 0:
            self._refuse_running_job("replace its container")
        name = shlex.quote(self.config.container)
        source = image_source(revision, self.config.dockerfile)
        build = f"docker build --label {self._label} -t {name} -f {shlex.quote(self.config.dockerfile)} -"
        print(f">> building {self.config.dockerfile} at {revision[:12]} on {self.name}")
        self._require(
            self.runner.pipe(["git", "archive", "--format=tar", revision], self._on_host(build)), "build the dev image"
        )
        checkout = shlex.quote(self._checkout)
        network = shlex.quote(self._network)
        run = " ".join(
            [
                f"docker run -d --name {name} --network {network} --init --restart unless-stopped",
                f"--label {IMAGE_LABEL}=$built --label {SOURCE_LABEL}={source}",
                f"-v {DOCKER_SOCKET}:{DOCKER_SOCKET} -v {shlex.quote(self._volume)}:{checkout}",
                f"{name} sleep infinity >/dev/null",
            ]
        )
        replace = f"docker rm -f {name} >/dev/null 2>&1; {run} || exit 1"
        current = f'[ "${{state#* }}" = "$built {source}" ] && [ "$joined" = {shlex.quote(self._network + " ")} ]'
        # Only a different image, or other image inputs, replace the container. Image IDs cannot tell:
        # a rebuild from cache gets a new one, and the image a container started from loses its ID
        # once the tag moves. Its layers and settings can, so the container carries their hash.
        # So does one on other networks than its own: benches join the container's network and call
        # its API back by its name, which only a user-defined network resolves, not Docker's bridge.
        script = "; ".join(
            [
                f"built=$(docker image inspect -f {shlex.quote(IMAGE_FINGERPRINT)} {name} | sha256sum)",
                "built=${built%% *}",
                f"docker network inspect {network} >/dev/null 2>&1 || docker network create {network} >/dev/null",
                f"state=$(docker container inspect -f {shlex.quote(CONTAINER_STATE)} {name} 2>/dev/null)",
                f"joined=$(docker container inspect -f {shlex.quote(CONTAINER_NETWORKS)} {name} 2>/dev/null)",
                f"if {current}; then :; else {replace}; fi",
                f"docker start {name} >/dev/null || exit 1",
                f"docker exec -u root {name} chown {CONTAINER_USER}: {checkout} || exit 1",
                f"docker image prune -f --filter label={self._label} >/dev/null",
            ]
        )
        self._require(self.runner.call(self._on_host(script)), "start the container")

    def remove(self) -> None:
        """Clean up what runs left on the machine's Docker, then remove the container, its volume, and images."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; there is nothing to remove")
        container = self.config.container
        if self._check_container() == 0:
            self._refuse_running_job("remove its container")
            path = shlex.quote(self.config.path)
            shell = shlex.join([*self.config.shell, "bash", "-c", "just stack-clean; just clean-workbenches 1"])
            if self.runner.call(self._ssh(f"cd {path} && if test -f justfile; then {shell}; fi")) != 0:
                print(f">> could not clean up what runs left on {self.name}; check its `docker ps -a`")
        name = shlex.quote(container)
        script = "; ".join(
            [
                f"docker rm -f {name} >/dev/null 2>&1",
                f"docker volume rm {shlex.quote(self._volume)} >/dev/null 2>&1",
                f"docker network rm {shlex.quote(self._network)} >/dev/null 2>&1",
                f"docker image ls -q --filter label={self._label} | xargs -r docker image rm -f >/dev/null",
                "true",
            ]
        )
        self._require(self.runner.call(self._on_host(script)), "remove the container")
        print(f">> removed {container}, its volume, network, and images from {self.name}")

    def job(self, revision: str, argv: Sequence[str]) -> tuple[int, list[Path]]:
        """Run ``argv`` at ``revision`` in the machine's checkout; its exit code, and the per-test runs it reported.

        On a remote machine, a job already there for the same commit and command is picked
        back up instead of started again.
        """
        if not self.remote:
            code, printed = self.runner.stream([*self.config.shell, *argv])
            return code, _reported_runs(printed)
        self._require_current_container(revision)
        command = shlex.join(argv)
        state = self._job_state(f"{revision} {command}")
        if state == THIS_JOB:
            print(f">> picking up `{command}` at {revision[:12]} on {self.name}")
        else:
            if state == OTHER_RUNNING:
                raise SystemExit(
                    f">> {self.name} is running the job above; rerun its command at its commit to follow it,"
                    f" or stop it: just cancel-e2e-on {self.name}"
                )
            if state == OTHER_UNFETCHED:
                print(
                    f">> the job above was never brought back from {self.name}; its runs stay in test-artifacts there"
                )
            if state == LOST_JOB:
                print(
                    f">> the job above died on {self.name} without an exit code: its container or the machine restarted"
                )
            self._ship(revision)
            self._start(f"{revision} {command}", argv)
        code, printed = self._follow()
        return code, _reported_runs(printed)

    def done(self) -> None:
        """Record that the job's results are here, so the same command starts it anew."""
        if self.remote:
            self._require(self.runner.call(self._ssh(f"touch {self._job}/fetched")), "record the job fetched")

    def cancel(self) -> None:
        """Interrupt the machine's job as Ctrl-C would, and kill what is left of it after two minutes."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; Ctrl-C stops its runs")
        if self._check_container() != 0:
            print(f">> {self.config.container} is not running on {self.name}, so neither is a job")
            return
        script = "; ".join(
            [
                self._job_alive,
                "alive || { echo '>> no job is running'; exit 0; }",
                f'pid=$(cat {self._job}/pid); echo ">> cancelling $(cat {self._job}/job)"',
                'kill -INT -- "-$pid"',
                'for _ in $(seq 120); do kill -0 -- "-$pid" 2>/dev/null || break; sleep 1; done',
                'kill -KILL -- "-$pid" 2>/dev/null',
                f"test -f {self._job}/exit || echo {INTERRUPTED} > {self._job}/exit",
                f"touch {self._job}/fetched",
            ]
        )
        self._require(self.runner.call(self._ssh(script)), "cancel the job")

    def _ship(self, revision: str) -> None:
        """Put ``revision`` on the machine, checked out clean."""
        path = shlex.quote(self.config.path)
        self._require(self.runner.call(self._ssh(f"test -d {path}/.git || {GIT} init -q {path}")), "prepare the clone")
        destination = f"{self.config.host}:{self.config.path}"
        self._require(
            self.runner.call(
                [
                    "git",
                    "-c",
                    f"core.sshCommand={shlex.join(['ssh', *SSH_OPTIONS])}",
                    "push",
                    "-q",
                    "--force",
                    f"--receive-pack={self._receive_pack}",
                    destination,
                    f"{revision}:refs/testbed/head",
                ]
            ),
            "push the commit",
        )
        self._require(
            self.runner.call(
                self._ssh(f"cd {path} && {GIT} checkout -q --detach --force {revision} && {GIT} clean -fdq")
            ),
            "check the commit out",
        )
        # The clone is ours, and so is the .envrc each commit brings: direnv runs it only once allowed.
        self._require(self.runner.call(self._ssh(f"cd {path} && direnv allow .")), "allow the commit's .envrc")

    def _start(self, job: str, argv: Sequence[str]) -> None:
        """Start ``argv`` in the checkout as the machine's job, in a process group of its own, detached from SSH."""
        line = shlex.join([*self.config.shell, *argv])
        body = f"cd {shlex.quote(self._checkout)} && {line} > {self._job}/log 2>&1; echo $? > {self._job}/exit"
        script = "\n".join(
            [
                f"rm -rf {self._job} && mkdir -p {self._job} || exit 1",
                f"printf '%s\\n' {shlex.quote(job)} > {self._job}/job",
                f": > {self._job}/log",
                # Job control gives the job its own process group, which cancelling interrupts as a whole.
                "set -m",
                f"nohup bash -c {shlex.quote(body)} </dev/null >/dev/null 2>&1 &",
                f"echo $! > {self._job}/pid",
                # With its pid, its start time: a restarted container can hand the pid to another process.
                f"cut -d' ' -f22 /proc/$!/stat > {self._job}/started",
            ]
        )
        self._require(self.runner.call(self._ssh(script)), "start the job")

    def _follow(self) -> tuple[int, list[str]]:
        """Show the job's log until it ends, reconnecting while the machine is unreachable; its exit code and lines."""
        printed: list[str] = []
        delay, unreachable = 5, 0
        while True:
            try:
                code, lines = self.runner.stream(self._ssh(self._follow_script(len(printed))))
            except KeyboardInterrupt:
                print(f"\n>> cancelling the job on {self.name}")
                self.cancel()
                return INTERRUPTED, []
            if lines and lines[-1].startswith(JOB_EXITED):
                return int(lines[-1].removeprefix(JOB_EXITED)), [*printed, *lines[:-1]]
            if lines and lines[-1] == JOB_LOST:
                raise SystemExit(
                    f">> the job on {self.name} died without an exit code: its container or the machine restarted"
                )
            printed += lines
            if code != SSH_FAILED:
                raise SystemExit(
                    f">> lost the job's output on {self.name} (exit {code}); it may still run there:"
                    " rerun the same command to pick it back up"
                )
            if lines:
                delay, unreachable = 5, 0
            if unreachable >= RECONNECT_SECONDS:
                raise SystemExit(
                    f">> could not reach {self.name} for {RECONNECT_SECONDS // 60} minutes; the job keeps running"
                    " there: rerun the same command to pick it back up"
                )
            print(f">> lost the connection to {self.name}; the job keeps running there, reconnecting in {delay}s")
            self.sleep(delay)
            unreachable += delay
            delay = min(delay * 2, 60)

    def _follow_script(self, seen: int) -> str:
        """The job's log after its first ``seen`` lines, as it grows while the job runs, then how it ended."""
        job, after = self._job, f"-n +{seen + 1}"
        return "; ".join(
            [
                self._job_alive,
                f'if alive; then tail {after} -f --pid="$(cat {job}/pid)" {job}/log; else tail {after} {job}/log; fi',
                f'if test -f {job}/exit; then echo "{JOB_EXITED}$(cat {job}/exit)"',
                f"else echo {shlex.quote(JOB_LOST)}; fi",
            ]
        )

    def _job_state(self, job: str) -> int:
        """0 if no job is there to pick up or wait for; else THIS_JOB, OTHER_RUNNING, OTHER_UNFETCHED, or LOST_JOB."""
        script = "; ".join(
            [
                self._job_alive,
                f"test -f {self._job}/job && ! test -f {self._job}/fetched || exit 0",
                f'test "$(cat {self._job}/job)" = {shlex.quote(job)} && this=1',
                f'if test -f {self._job}/exit || alive; then test -n "$this" && exit {THIS_JOB}',
                f'echo ">> on {self.name}: $(cat {self._job}/job)"',
                f"test -f {self._job}/exit && exit {OTHER_UNFETCHED}",
                f"exit {OTHER_RUNNING}; fi",
                f'echo ">> on {self.name}: $(cat {self._job}/job)"',
                f"exit {LOST_JOB}",
            ]
        )
        code = self.runner.call(self._ssh(script))
        if code not in (0, THIS_JOB, OTHER_RUNNING, OTHER_UNFETCHED, LOST_JOB):
            self._require(code, "look for a job")
        return code

    def _refuse_running_job(self, what: str) -> None:
        if self._job_state("") == OTHER_RUNNING:
            raise SystemExit(
                f">> {self.name} is running the job above, so this will not {what};"
                f" let it end, or stop it: just cancel-e2e-on {self.name}"
            )

    @property
    def _job(self) -> str:
        return shlex.quote(f"{self._checkout}/{JOB}")

    @property
    def _job_alive(self) -> str:
        """A shell function: whether the job's process still runs (and is the job's, by its start time)."""
        return (
            f'alive() {{ pid=$(cat {self._job}/pid 2>/dev/null) && test -n "$pid"'
            f' && test "$(cut -d" " -f22 /proc/$pid/stat 2>/dev/null)" = "$(cat {self._job}/started)"; }}'
        )

    def fetch_run(self, run: Path) -> Path:
        """Bring a run the machine wrote into this checkout's test-artifacts; where it now is."""
        if not self.remote:
            return run
        local = ROOT / "test-artifacts" / _after_test_artifacts(run)
        local.parent.mkdir(parents=True, exist_ok=True)
        excludes = [f"--exclude={pattern}" for pattern in SLIM_EXCLUDES] if self.config.fetch == "slim" else []
        archive = " ".join(["tar", "-cf", "-", *excludes, "-C", shlex.quote(str(run.parent)), shlex.quote(run.name)])
        self._require(
            self.runner.pipe(self._ssh(archive), ["tar", "-xf", "-", "-C", str(local.parent)]), f"fetch {run.name}"
        )
        return local

    def fetch_receipt(self) -> None:
        if not self.remote:
            return
        receipt = ROOT / RECEIPT
        receipt.parent.mkdir(parents=True, exist_ok=True)
        archive = f"tar -cf - -C {shlex.quote(self.config.path)} {RECEIPT}"
        self._require(self.runner.pipe(self._ssh(archive), ["tar", "-xf", "-", "-C", str(ROOT)]), "fetch the receipt")

    def _ssh(self, command: str) -> list[str]:
        """``command`` where the machine's work happens: in a login shell in its container, from its user's home."""
        return self._on_host(f"{self._exec} bash -lc {shlex.quote(command)}")

    def _on_host(self, command: str) -> list[str]:
        """``command`` on the host, in a login shell: a plain ssh command sees no profile, so often no Nix."""
        return ["ssh", *SSH_OPTIONS, self.config.host or "", f"bash -lc {shlex.quote(command)}"]

    @property
    def _exec(self) -> str:
        return shlex.join(["docker", "exec", "-i", "-u", CONTAINER_USER, "-w", CONTAINER_HOME, self.config.container])

    @property
    def _receive_pack(self) -> str:
        """What a push runs on the machine: in the container, Git's appended path passed on by ``docker exec``."""
        return f"{self._exec} {RECEIVE_PACK}"

    @property
    def _checkout(self) -> str:
        return self.config.path if self.config.path.startswith("/") else f"{CONTAINER_HOME}/{self.config.path}"

    @property
    def _network(self) -> str:
        return f"{self.config.container}-network"

    @property
    def _volume(self) -> str:
        return f"{self.config.container}-checkout"

    @property
    def _label(self) -> str:
        return shlex.quote(f"repo2ree.dev-container={self.config.container}")

    def _check_container(self, source: str | None = None) -> int:
        """0 if the container runs (and was built from ``source``, if given); else NOT_RUNNING or OTHER_SOURCE."""
        inspect = f"docker container inspect -f {shlex.quote(CONTAINER_STATE)} {shlex.quote(self.config.container)}"
        script = "; ".join(
            [
                f"state=$({inspect} 2>/dev/null) || exit {NOT_RUNNING}",
                f'[ "${{state%% *}}" = true ] || exit {NOT_RUNNING}',
                *([f'[ "${{state##* }}" = {source} ] || exit {OTHER_SOURCE}'] if source else []),
            ]
        )
        code = self.runner.call(self._on_host(script))
        if code == SSH_FAILED:
            raise SystemExit(
                f">> could not reach {self.name} as {self.config.host} over SSH; is your key in the agent"
                f" (ssh-add -l), and its host key in {KNOWN_HOSTS.relative_to(ROOT)}? tools/ssh/setup-vm.sh puts both"
            )
        return code

    def _require_current_container(self, revision: str) -> None:
        code = self._check_container(image_source(revision, self.config.dockerfile))
        prepare = f"run: just prepare-e2e-machine {self.name}"
        if code == NOT_RUNNING:
            raise SystemExit(f">> {self.config.container} is not running on {self.name}; {prepare}")
        if code == OTHER_SOURCE:
            raise SystemExit(
                f">> {self.config.container} on {self.name} was built from other image inputs than"
                f" {self.config.dockerfile} and what it copies at {revision[:12]}; {prepare}"
            )
        self._require(code, "check the container")

    def _require(self, code: int, what: str) -> None:
        if code != 0:
            raise SystemExit(f">> could not {what} on {self.name} (exit {code})")


def _reported_runs(printed: Sequence[str]) -> list[Path]:
    return [Path(line.removeprefix(RUN_LINE).strip()) for line in printed if line.startswith(RUN_LINE)]


def _after_test_artifacts(run: Path) -> Path:
    """A run's path below test-artifacts/, wherever the machine keeps its checkout."""
    parts = run.parts
    if "test-artifacts" not in parts:
        raise SystemExit(f">> {run} is not under a test-artifacts directory")
    return Path(*parts[len(parts) - parts[::-1].index("test-artifacts") :])


def image_inputs(dockerfile: str) -> list[str]:
    """What a Dockerfile copies from its context, as paths there; ``.`` for a pattern or the whole context."""
    paths: list[str] = []
    for line in re.sub(r"\\\n", " ", dockerfile).splitlines():
        words = line.split()
        if not words or words[0].upper() not in ("COPY", "ADD") or any(w.startswith("--from") for w in words):
            continue
        rest = line.split(None, 1)[1].strip()
        while rest.startswith("--"):
            rest = rest.split(None, 1)[1].strip()
        sources = json.loads(rest)[:-1] if rest.startswith("[") else rest.split()[:-1]
        for source in sources:
            path = source.removeprefix("./").strip("/")
            paths.append("." if not path or any(c in path for c in "*?[") else path)
    return paths


def image_source(revision: str, dockerfile: str) -> str:
    """A hash of what the dev image is built from at ``revision``: the Dockerfile and every path it copies."""
    objects = []
    for path in sorted({dockerfile, *image_inputs(capture(["git", "show", f"{revision}:{dockerfile}"]))}):
        spec = f"{revision}^{{tree}}" if path == "." else f"{revision}:{path}"
        objects.append(f"{path} {capture(['git', 'rev-parse', spec])}")
    return hashlib.sha256("\n".join(objects).encode()).hexdigest()[:16]


def committed_head() -> str:
    """HEAD, refusing uncommitted changes: what a machine runs is a commit, so nothing else may count."""
    if capture(["git", "status", "--porcelain"]):
        raise SystemExit(">> the working tree is not clean; commit first, since a machine runs a commit")
    return capture(["git", "rev-parse", "HEAD"])


def gate(machine: Machine, jobs: int | None) -> int:
    code, runs = machine.job(committed_head(), ["just", "assurance-gate", str(jobs or machine.config.jobs)])
    _bring_back(machine, runs)
    if code == 0:
        machine.fetch_receipt()
        print(f">> assurance-gate receipt from {machine.name}: {RECEIPT}")
    machine.done()
    return code


def run_recipe(machine: Machine, recipe: Sequence[str]) -> int:
    revision = committed_head() if machine.remote else "HEAD"
    code, runs = machine.job(revision, ["just", *recipe])
    _bring_back(machine, runs)
    machine.done()
    return code


def _bring_back(machine: Machine, runs: Sequence[Path]) -> None:
    for run in runs:
        print(f">> run from {machine.name}: {machine.fetch_run(run).relative_to(ROOT)}")


def prepare(machine: Machine) -> int:
    revision = committed_head()
    machine.provision(revision)
    code, _ = machine.job(revision, ["just", "build-e2e-bundles"])
    machine.done()
    return code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed machine", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the machines")
    commands.add_parser(
        "prepare", help="start its container from HEAD, ship HEAD into it, and build the bundles"
    ).add_argument("machine")
    commands.add_parser(
        "remove", help="clean up its container's runs, then remove the container, its volume, and images"
    ).add_argument("machine")
    commands.add_parser("cancel", help="stop the job running there, as Ctrl-C on its run would").add_argument("machine")
    gating = commands.add_parser("gate", help="run the assurance gate there and bring its receipt and runs back")
    gating.add_argument("machine")
    gating.add_argument("--jobs", type=int, help="stacks side by side per tier (default: the machine's)")
    running = commands.add_parser("run", help="run a just recipe there and bring back the per-test runs it made")
    running.add_argument("machine")
    running.add_argument("recipe", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    path = machines_file()
    machines = load_machines(path)
    if args.command == "list":
        for name, config in machines.items():
            where = f"{config.host}:{config.path}" if config.host else config.path
            inside = f"  container={config.container}" if config.host else ""
            print(f"{name:12} {where}  jobs={config.jobs}{inside}")
        return 0
    if args.machine not in machines:
        raise SystemExit(f">> no machine {args.machine!r}; known: {', '.join(machines)} (from {path})")
    machine = Machine(args.machine, machines[args.machine])
    if args.command == "prepare":
        return prepare(machine)
    if args.command == "remove":
        machine.remove()
        return 0
    if args.command == "cancel":
        machine.cancel()
        return 0
    if args.command == "gate":
        return gate(machine, args.jobs)
    if not args.recipe:
        parser.error("run needs a recipe")
    return run_recipe(machine, args.recipe)


if __name__ == "__main__":
    raise SystemExit(main())

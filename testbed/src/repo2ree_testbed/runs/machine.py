"""``python -m repo2ree_testbed machine``: run the gate or a tier on a machine, here or over SSH.

A machine is where the stacks run. ``local`` is this checkout; any other is an SSH
machine named in the machines file (``$REPO2REE_MACHINES``, by default the untracked
``.config/machines.toml`` of this checkout), since hosts are a developer's own:

    [machines.vm]
    host = "vm"          # an ssh destination: an alias, or user@host
    jobs = 6             # stacks side by side per tier

A remote machine works as this checkout does: a clone (~/repo2ree of its SSH user) and
the dev container brought up from it with Compose (docker-compose.dev.yml, with
docker/dev/machine.compose.yml over it, which keeps it up for runs), where every
command runs in the clone's .envrc. It needs Git and a Docker Engine with Compose
that its SSH user may use.

A run pushes HEAD to the clone, checks it out, brings the container up, and starts the
recipe in it detached, as the machine's one job: its command, log, and exit code are in
test-artifacts/machine-job/ of the clone. It shows the log until the job ends, then
brings back what the job wrote: every file under test-artifacts/, .receipts/, and logs/ changed
since it started, which in a clone that runs one job at a time is exactly its results,
whatever the recipe (runs, recordings, coverage, and receipts, which bind a tree rather
than a machine), but for runtime tarballs and archives, which stay there. Ctrl-C or a
dropped connection only stops the showing: the job goes on, and the next run on that
machine shows it again and brings its results back before starting anything of its own.
`cancel` stops the job; `remove` takes the container down and deletes the clone.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.machines import MachineConfig, load_machines, machines_file
from repo2ree_testbed.stack.process import capture

# The clone, in the SSH user's home, which the dev container mounts at /repo2ree.
CLONE = "repo2ree"
CONTAINER_USER = "nixuser"
COMPOSE_FILES = ("docker-compose.dev.yml", "docker/dev/machine.compose.yml")
SERVICE = "dev"
# The machine's one job, in the clone: what it runs, its log, its exit code, and whether
# its results were brought back.
JOB = "test-artifacts/machine-job"
# Where a machine's image archive sets are (just archive-images): one directory per platform.
ARCHIVES = "dist/images"
SSH_FAILED = 255
INTERRUPTED = 130
# The machines' host keys, kept beside the machines file by tools/ssh/setup-vm.sh, so they
# outlive a rebuilt dev container; a host in neither file is refused, not asked about. A
# connection that cannot be made, or that stops answering, fails within a minute.
KNOWN_HOSTS = ROOT / ".config" / "known_hosts"
SSH_OPTIONS = (
    *("-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4"),
    *("-o", f"UserKnownHostsFile={KNOWN_HOSTS} ~/.ssh/known_hosts", "-o", "StrictHostKeyChecking=yes"),
)
# What a slim fetch leaves on the machine: the bulk of a run, and nothing a verdict or a page reads.
SLIM_EXCLUDES = (
    "! -name '*.tar'",
    "! -name '*.tar.gz'",
    "! -name '*.tgz'",
    "! -path '*/artifacts/archives/*'",
    # The REE archives a GUI test kept (helpers/flow.ts keepReeArchive): their histories are in the
    # dossier already, and the machine keeps the archives, which carry every runtime payload.
    "! -path '*/artifacts/*/ree*.zip'",
)
# What every command on a remote machine runs in: the clone's .envrc, as here, with the venv it syncs.
SHELL = ("direnv", "exec", ".")
# The Compose project of a remote machine's dev container.
PROJECT = "repo2ree-dev"
# How long `gc` keeps build cache nothing used: what the dev image and the stacks' images rebuild from
# today. By age, not size: most of the cache is shared with images, and a size cap removes nothing.
CACHE_KEPT_FOR = "24h"
# How long `gc` keeps an image nothing runs: a week of rebuilds stays warm.
IMAGES_KEPT_FOR = "168h"


class Runner(Protocol):
    def call(self, argv: Sequence[str]) -> int: ...

    def capture(self, argv: Sequence[str]) -> tuple[int, str]: ...

    def pipe(self, producer: Sequence[str], consumer: Sequence[str]) -> int: ...


class Processes:
    def call(self, argv: Sequence[str]) -> int:
        return subprocess.run(list(argv), cwd=ROOT, check=False).returncode

    def capture(self, argv: Sequence[str]) -> tuple[int, str]:
        done = subprocess.run(list(argv), cwd=ROOT, check=False, stdout=subprocess.PIPE, text=True)
        return done.returncode, done.stdout

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


@dataclass(frozen=True)
class Job:
    """The machine's job: ``none``, ``running``, ``ended`` (results not yet here), ``fetched``, or ``dead``."""

    state: str
    command: str = ""


@dataclass
class Machine:
    """One machine, reached the way its kind is reached."""

    name: str
    config: MachineConfig
    runner: Runner = field(default_factory=Processes)

    @property
    def remote(self) -> bool:
        return self.config.host is not None

    def run(self, revision: str, argv: Sequence[str]) -> int:
        """Run ``argv`` at ``revision`` on the machine and bring its results back; its exit code."""
        if not self.remote:
            return self.runner.call(argv)
        command = f"{revision} {shlex.join(argv)}"
        job = self.job()
        if job.state == "running":
            print(f">> {self.name} is running `{job.command}`; showing it")
            if not self._show():
                return INTERRUPTED
            code = self._bring_back(self.job())
            if job.command != command:
                print(f">> that job ended; run yours again to start it on {self.name}")
                return 1
            return code
        if job.state == "ended":
            code = self._bring_back(job)
            if job.command == command:
                return code
        if job.state == "dead":
            print(f">> `{job.command}` died on {self.name} without an exit code: its container restarted")
        self._ship(revision)
        self._up()
        self._start(command, argv)
        if not self._show():
            return INTERRUPTED
        return self._bring_back(self.job())

    def job(self) -> Job:
        alive = f"{self._compose} exec -T {SERVICE} sh -c {shlex.quote(_ALIVE)} 2>/dev/null"
        script = "; ".join(
            [
                f"cd {CLONE} 2>/dev/null && test -f {JOB}/command || {{ echo none; exit 0; }}",
                f"if test -f {JOB}/fetched; then echo fetched; elif test -f {JOB}/exit; then echo ended",
                f"elif {alive}; then echo running; else echo dead; fi",
                f"cat {JOB}/command",
            ]
        )
        code, output = self.runner.capture(self._on_host(script))
        if code == SSH_FAILED:
            raise SystemExit(
                f">> could not reach {self.name} as {self.config.host} over SSH; is your key in the agent"
                f" (ssh-add -l), and its host key in {KNOWN_HOSTS.relative_to(ROOT)}? tools/ssh/setup-vm.sh puts both"
            )
        self._require(code, "look for its job")
        state, _, command = output.strip().partition("\n")
        return Job(state, command.strip())

    def cancel(self) -> None:
        """Stop the machine's job by restarting its container, and clean up the stacks it left."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; Ctrl-C stops its runs")
        job = self.job()
        if job.state != "running":
            print(f">> {self.name} is running no job")
            return
        print(f">> cancelling `{job.command}` on {self.name}")
        cleanup = shlex.join([*SHELL, "bash", "-c", "just stack-clean; just clean-workbenches"])
        script = " && ".join(
            [
                f"{self._compose} restart {SERVICE}",
                f"{self._compose} up -d --wait",
                f"{{ test -f {JOB}/exit || echo {INTERRUPTED} > {JOB}/exit; }}",
                f"touch {JOB}/fetched",
                f"{self._exec} bash -lc {shlex.quote(cleanup)}",
            ]
        )
        self._require(self.runner.call(self._in_clone(script)), "cancel the job")

    def remove(self) -> None:
        """Clean up what runs left on the machine's Docker, take the container down, and delete the clone."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; there is nothing to remove")
        if self.job().state == "running":
            raise SystemExit(f">> {self.name} is running a job; let it end, or: just machine cancel {self.name}")
        cleanup = shlex.join([*SHELL, "bash", "-c", "just stack-clean; just clean-workbenches 1"])
        script = "; ".join(
            [
                f"test -d {CLONE} || exit 0",
                f"cd {CLONE}",
                f"{self._exec} bash -lc {shlex.quote(cleanup)} 2>/dev/null",
                f"{self._compose} down --volumes --remove-orphans --rmi local || exit 1",
                f"cd && rm -rf {CLONE}",
            ]
        )
        self._require(self.runner.call(self._on_host(script)), "remove the container")
        print(f">> removed the dev container, its images, and the clone from {self.name}")

    def gc(self) -> None:
        """Bound what the machine keeps: the clone's generated trees, Docker's build cache, unused images.

        In the clone, the stacks runs left and every generated tree's own prune (`just prune`); on
        the host, build cache unused for CACHE_KEPT_FOR and images nothing runs that are older than
        IMAGES_KEPT_FOR. The running dev container and its image stay, and so do the bundle
        stores, which the testbed prunes itself.
        """
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; run `just prune` here")
        if self.job().state == "running":
            raise SystemExit(f">> {self.name} is running a job; let it end, or: just machine cancel {self.name}")
        # A clone of a commit before `just prune` existed skips it rather than failing on it.
        steps = "just stack-clean; just clean-workbenches; just --show prune >/dev/null 2>&1 && just prune"
        clone = shlex.join([*SHELL, "bash", "-c", steps])
        script = "; ".join(
            [
                "df -h / | tail -n 1",
                f"(test -d {CLONE} && cd {CLONE} && {self._exec} bash -lc {shlex.quote(clone)})",
                f"docker builder prune -a -f --filter until={CACHE_KEPT_FOR} > /dev/null",
                f"docker image prune -a -f --filter until={IMAGES_KEPT_FOR} > /dev/null",
                "docker system df",
                "df -h / | tail -n 1",
            ]
        )
        self._require(self.runner.call(self._on_host(script)), "collect garbage")

    def _ship(self, revision: str) -> None:
        """Put ``revision`` in the machine's clone, checked out clean."""
        init = f"test -d {CLONE}/.git || git init -q {CLONE}"
        self._require(self.runner.call(self._on_host(init)), "prepare the clone")
        ssh = shlex.join(["ssh", *SSH_OPTIONS])
        destination = f"{self.config.host}:{CLONE}"
        push = [
            "git",
            "-c",
            f"core.sshCommand={ssh}",
            "push",
            "-q",
            "--force",
            destination,
            f"{revision}:refs/testbed/head",
        ]
        self._require(self.runner.call(push), "push the commit")
        checkout = f"git checkout -q --detach --force {revision} && git clean -fdq"
        self._require(self.runner.call(self._in_clone(checkout)), "check the commit out")

    def _up(self) -> None:
        """Bring the dev container up and wait until its user is set up; Compose rebuilds only what changed."""
        up = f"{self._compose} up -d --build --quiet-pull --wait"
        self._require(self.runner.call(self._in_clone(up)), "bring the dev container up")

    def _start(self, command: str, argv: Sequence[str]) -> None:
        """Start ``argv`` in the dev container as the machine's job, detached from this connection.

        The job knows the machine by name, so what it records (logs/just/) says where it ran.
        """
        machine = f"REPO2REE_MACHINE={shlex.quote(self.name)}"
        body = f"{machine} {shlex.join([*SHELL, *argv])} > {JOB}/log 2>&1; echo $? > {JOB}/exit"
        script = " && ".join(
            [
                f"rm -rf {JOB} && mkdir -p {JOB}",
                f"printf '%s\\n' {shlex.quote(command)} > {JOB}/command",
                f": > {JOB}/log",
                f"{self._compose} exec -d --user {CONTAINER_USER} {SERVICE} bash -lc {shlex.quote(body)}",
            ]
        )
        self._require(self.runner.call(self._in_clone(script)), "start the job")

    def _show(self) -> bool:
        """Show the job's log until it ends; False if Ctrl-C or a lost connection stopped the showing first."""
        alive = f"{self._compose} exec -T {SERVICE} sh -c {shlex.quote(_ALIVE)} 2>/dev/null"
        script = "; ".join(
            [
                f"cd {CLONE} || exit 1",
                f"tail -n +1 -f {JOB}/log & shown=$!",
                f"while ! test -f {JOB}/exit && {alive}; do sleep 5; done",
                "sleep 1; kill $shown",
            ]
        )
        again = f"run it again to show the job and bring its results back, or: just machine cancel {self.name}"
        try:
            code = self.runner.call(self._on_host(script))
        except KeyboardInterrupt:
            print(f"\n>> stopped showing; the job goes on on {self.name}: {again}")
            return False
        if code == SSH_FAILED:
            print(f">> lost the connection to {self.name}; the job goes on there: {again}")
            return False
        return True

    def _bring_back(self, job: Job) -> int:
        """Bring back what the ended job wrote; the job's exit code.

        A run claims the results first (``mkdir`` succeeds for one caller only), so a second run
        started meanwhile does not copy the same files again beside it.
        """
        read, exit_line = self.runner.capture(self._in_clone(f"cat {JOB}/exit 2>/dev/null; echo"))
        self._require(read, "read the job's exit code")
        code = int(exit_line) if exit_line.strip() else None
        if self.runner.call(self._in_clone(f"mkdir {JOB}/fetching 2>/dev/null")) != 0:
            print(f">> another run is already bringing back `{job.command}` from {self.name}; not copying it twice")
            return 1 if code is None else code
        read, listed = self.runner.capture(self._in_clone(self._written))
        self._require(read, "list what the job wrote")
        written = [line for line in listed.splitlines() if line]
        if written:
            archive = self._in_clone(f"{self._written} | tar -cf - -T -")
            self._require(self.runner.pipe(archive, ["tar", "-xf", "-", "-C", str(ROOT)]), "bring back its results")
            for result in _results(written):
                print(f">> from {self.name}: {result}")
        if code is None:
            print(f">> `{job.command}` died on {self.name} without an exit code: its container restarted")
        self._require(self.runner.call(self._in_clone(f"touch {JOB}/fetched")), "record the job fetched")
        return 1 if code is None else code

    @property
    def _written(self) -> str:
        """Lists the files the job wrote: under test-artifacts/, .receipts/, and logs/, changed since it started."""
        tests = " ".join(["-type f", f"-cnewer {JOB}/command", f"! -path '{JOB}/*'", *SLIM_EXCLUDES])
        return f"{{ find test-artifacts .receipts logs {tests} 2>/dev/null || true; }}"

    @property
    def _compose(self) -> str:
        files = " ".join(f"-f {path}" for path in COMPOSE_FILES)
        return f"docker compose --project-name {PROJECT} {files}"

    @property
    def _exec(self) -> str:
        return f"{self._compose} exec -T --user {CONTAINER_USER} {SERVICE}"

    def _in_clone(self, command: str) -> list[str]:
        return self._on_host(f"cd {CLONE} && {command}")

    def _on_host(self, command: str) -> list[str]:
        """``command`` on the host, in a login shell from its user's home: a plain ssh command sees no profile."""
        return ["ssh", *SSH_OPTIONS, self.config.host or "", f"bash -lc {shlex.quote(command)}"]

    def fetch_archives(self) -> int:
        """Bring the machine's image archive sets here, replacing this checkout's set for each platform it has."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; its archives are in {ARCHIVES} already")
        listed, names = self.runner.capture(self._in_clone(f"ls {ARCHIVES} 2>/dev/null; true"))
        self._require(listed, "list its image archives")
        platforms = [name for name in names.split() if not name.startswith(".")]
        if not platforms:
            print(f">> {self.name} has no image archives: run just archive-images there after its publish gate")
            return 1
        (ROOT / ARCHIVES).mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".fetching-", dir=ROOT / ARCHIVES))
        try:
            archive = self._in_clone(f"tar -cf - -C {ARCHIVES} {shlex.join(platforms)}")
            self._require(self.runner.pipe(archive, ["tar", "-xf", "-", "-C", str(staging)]), "bring back its archives")
            for platform in platforms:
                target = ROOT / ARCHIVES / platform
                shutil.rmtree(target, ignore_errors=True)
                (staging / platform).rename(target)
                print(f">> from {self.name}: {ARCHIVES}/{platform}")
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return 0

    def _require(self, code: int, what: str) -> None:
        if code != 0:
            raise SystemExit(f">> could not {what} on {self.name} (exit {code})")


# Whether the job's process is still there, in the dev container: its command line names
# the exit file it will write. The brackets keep this grep from finding itself.
_ALIVE = f"grep -qs {shlex.quote(JOB.replace('job', 'jo[b]') + '/exit')} /proc/[0-9]*/cmdline"


def _results(written: Sequence[str]) -> list[str]:
    """What the written files amount to: each run's directory (test-artifacts/<kind>/<run>), or the file."""
    return list(dict.fromkeys(str(Path(*Path(path).parts[:3])) for path in written))


def committed_head() -> str:
    """HEAD, refusing uncommitted changes: what a machine runs is a commit, so nothing else may count."""
    if capture(["git", "status", "--porcelain"]):
        raise SystemExit(
            ">> the working tree is not clean; commit first, since a machine runs a commit"
            " (or `just on-wip` to run the working tree as a commit of its own)"
        )
    return capture(["git", "rev-parse", "HEAD"])


# The author of a working-tree commit when the developer has configured none.
WIP_IDENTITY = {
    "GIT_AUTHOR_NAME": "repo2ree testbed",
    "GIT_AUTHOR_EMAIL": "testbed@invalid",
    "GIT_COMMITTER_NAME": "repo2ree testbed",
    "GIT_COMMITTER_EMAIL": "testbed@invalid",
}


def working_tree_commit() -> str:
    """The working tree as a commit on HEAD, made beside the branch: neither HEAD nor the index moves.

    It holds what ``git add -A`` would stage, untracked files included and ignored ones not.
    Nothing but the machine's ``refs/testbed/head`` reaches it, and a receipt it earns binds
    its tree, which only a commit of exactly that content can claim. A clean tree is HEAD.
    """
    if not capture(["git", "status", "--porcelain"]):
        return capture(["git", "rev-parse", "HEAD"])
    with tempfile.TemporaryDirectory() as scratch:
        index = {**os.environ, "GIT_INDEX_FILE": str(Path(scratch) / "index")}
        capture(["git", "read-tree", "HEAD"], env=index, check=True)
        capture(["git", "add", "-A"], env=index, check=True)
        tree = capture(["git", "write-tree"], env=index, check=True)
    author = {} if capture(["git", "config", "user.email"]) else WIP_IDENTITY
    message = "work in progress, run on a machine"
    return capture(["git", "commit-tree", tree, "-p", "HEAD", "-m", message], env={**os.environ, **author}, check=True)


def gate(machine: Machine, jobs: int | None) -> int:
    return run_recipe(machine, ["assurance-gate", str(jobs or machine.config.jobs)])


def run_recipe(machine: Machine, recipe: Sequence[str], *, wip: bool = False) -> int:
    """Run ``recipe`` there: HEAD, or with ``wip`` the working tree as a commit of its own."""
    if not machine.remote:
        return machine.run("HEAD", ["just", *recipe])
    return machine.run(working_tree_commit() if wip else committed_head(), ["just", *recipe])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed machine", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the machines")
    commands.add_parser(
        "remove", help="clean up its container's runs, take the container down, and delete the clone"
    ).add_argument("machine")
    commands.add_parser("cancel", help="stop the job running there").add_argument("machine")
    commands.add_parser(
        "gc", help="prune the clone's generated trees, Docker's build cache, and unused images there"
    ).add_argument("machine")
    commands.add_parser(
        "fetch-archives", help="bring its image archive sets (just archive-images) here, for publish-candidate"
    ).add_argument("machine")
    gating = commands.add_parser("gate", help="run the assurance gate there and bring its receipt and runs back")
    gating.add_argument("machine")
    gating.add_argument("--jobs", type=int, help="stacks side by side per tier (default: the machine's)")
    running = commands.add_parser("run", help="run a just recipe there and bring back what it wrote")
    running.add_argument("--wip", action="store_true", help="run the working tree, committed beside the branch")
    running.add_argument("machine")
    running.add_argument("recipe", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    path = machines_file()
    machines = load_machines(path)
    if args.command == "list":
        for name, config in machines.items():
            where = f"{config.host}:~/{CLONE}" if config.host else str(ROOT)
            print(f"{name:12} {where}  jobs={config.jobs}")
        return 0
    if args.machine not in machines:
        raise SystemExit(f">> no machine {args.machine!r}; known: {', '.join(machines)} (from {path})")
    machine = Machine(args.machine, machines[args.machine])
    if args.command == "remove":
        machine.remove()
        return 0
    if args.command == "cancel":
        machine.cancel()
        return 0
    if args.command == "gc":
        machine.gc()
        return 0
    if args.command == "gate":
        return gate(machine, args.jobs)
    if args.command == "fetch-archives":
        return machine.fetch_archives()
    if not args.recipe:
        parser.error("run needs a recipe")
    return run_recipe(machine, args.recipe, wip=args.wip)


if __name__ == "__main__":
    raise SystemExit(main())

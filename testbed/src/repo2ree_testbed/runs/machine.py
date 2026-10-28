"""``python -m repo2ree_testbed machine``: run the gate or a tier on a machine, here or over SSH.

A machine is where the stacks run. ``local`` is this checkout; any other is an SSH
machine named in the machines file (``$REPO2REE_MACHINES``, by default the untracked
``.config/machines.toml`` of this checkout), since hosts are a developer's own:

    [machines.vm]
    host = "vm"          # an ssh destination: an alias, or user@host
    jobs = 6             # stacks side by side per tier
    # shell = [...]      what every command runs inside; by default the clone's .envrc, via direnv
    # fetch = "slim"     # or "full": "slim" leaves runtime tarballs and archives behind
    # container = "repo2ree-dev"    the Compose project of the dev container there

A remote machine works as this checkout does: a clone (~/repo2ree of its SSH user), and
the dev container brought up from it with Compose, mounting it at /repo2ree. It needs
Git and a Docker Engine with Compose that its SSH user may use. A run pushes HEAD to the
clone, checks it out clean, brings the container up (docker-compose.dev.yml, with
docker/dev/machine.compose.yml over it, which builds the Nix dev image: Compose rebuilds
it when its inputs changed and keeps the container otherwise), runs the recipe in the
container's dev shell, and sends back every per-test run the recipe reported; the gate
also sends back its receipt, which binds a tree rather than a machine, so it holds here
as it did there. Only a commit can be shipped, so the repository needs to be committed.
`remove` cleans up what runs left on that Docker, takes the Compose project down, and
deletes the clone.

On a remote machine the recipe runs as a job detached from SSH: its output goes to a
log in the clone's test-artifacts, which the run follows. A dropped connection only
stops the following; the run reconnects for a while, and after that the same command
again, at the same commit, picks the job back up, or its results once it ended. One
job runs at a time: anything else that would touch the clone or the container refuses
while one does. Ctrl-C cancels the job; `cancel` does so from anywhere.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.machines import MachineConfig, load_machines, machines_file
from repo2ree_testbed.stack.process import capture

RUN_LINE = ">> per-test run: "
RECEIPT = ".receipts/assurance-gate.json"
# The clone, in the SSH user's home, and where the dev container mounts it, as the local
# dev container mounts its checkout; the dev image's direnv trusts the .envrc there.
CLONE = "repo2ree"
CHECKOUT = "/repo2ree"
CONTAINER_USER = "nixuser"
# The dev container's Compose files, in the clone, and its service.
COMPOSE_FILES = ("docker-compose.dev.yml", "docker/dev/machine.compose.yml")
SERVICE = "dev"
# What ssh exits with when it cannot connect or log in, as opposed to the remote command failing.
SSH_FAILED = 255
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

    def remove(self) -> None:
        """Clean up what runs left on the machine's Docker, take the Compose project down, and delete the clone."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; there is nothing to remove")
        if self._container_up():
            self._refuse_running_job("remove its container")
            shell = shlex.join([*self.config.shell, "bash", "-c", "just stack-clean; just clean-workbenches 1"])
            if self.runner.call(self._ssh(shell)) != 0:
                print(f">> could not clean up what runs left on {self.name}; check its `docker ps -a`")
        down = f"{self._compose} down --volumes --remove-orphans --rmi local"
        script = f"if test -d {CLONE}; then (cd {CLONE} && {down}) || exit 1; rm -rf {CLONE}; fi"
        self._require(self.runner.call(self._on_host(script)), "remove the container")
        print(f">> removed the dev container, its images, and the clone from {self.name}")

    def job(self, revision: str, argv: Sequence[str]) -> tuple[int, list[Path]]:
        """Run ``argv`` at ``revision`` in the machine's checkout; its exit code, and the per-test runs it reported.

        On a remote machine, a job already there for the same commit and command is picked
        back up instead of started again.
        """
        if not self.remote:
            code, printed = self.runner.stream([*self.config.shell, *argv])
            return code, _reported_runs(printed)
        command = shlex.join(argv)
        state = self._job_state(f"{revision} {command}") if self._container_up() else 0
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
            self._up()
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
        if not self._container_up():
            print(f">> the dev container is not running on {self.name}, so neither is a job")
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
        """Put ``revision`` in the machine's clone, checked out clean."""
        self._require(
            self.runner.call(self._on_host(f"test -d {CLONE}/.git || git init -q {CLONE}")), "prepare the clone"
        )
        self._require(
            self.runner.call(
                [
                    "git",
                    "-c",
                    f"core.sshCommand={shlex.join(['ssh', *SSH_OPTIONS])}",
                    "push",
                    "-q",
                    "--force",
                    f"{self.config.host}:{CLONE}",
                    f"{revision}:refs/testbed/head",
                ]
            ),
            "push the commit",
        )
        checkout = f"git checkout -q --detach --force {revision} && git clean -fdq"
        self._require(self.runner.call(self._in_clone(checkout)), "check the commit out")

    def _up(self) -> None:
        """Bring the dev container up from the clone: Compose builds what changed and keeps what did not."""
        self._require(
            self.runner.call(self._in_clone(f"{self._compose} up -d --build --quiet-pull")),
            "bring the dev container up",
        )

    def _start(self, job: str, argv: Sequence[str]) -> None:
        """Start ``argv`` in the checkout as the machine's job, in a process group of its own, detached from SSH."""
        line = shlex.join([*self.config.shell, *argv])
        body = f"{line} > {self._job}/log 2>&1; echo $? > {self._job}/exit"
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
        return shlex.quote(f"{CHECKOUT}/{JOB}")

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
        below = _after_test_artifacts(run)
        local = ROOT / "test-artifacts" / below
        local.parent.mkdir(parents=True, exist_ok=True)
        excludes = [f"--exclude={pattern}" for pattern in SLIM_EXCLUDES] if self.config.fetch == "slim" else []
        there = shlex.quote(f"{CLONE}/test-artifacts/{below.parent}")
        archive = " ".join(["tar", "-cf", "-", *excludes, "-C", there, shlex.quote(below.name)])
        self._require(
            self.runner.pipe(self._on_host(archive), ["tar", "-xf", "-", "-C", str(local.parent)]), f"fetch {run.name}"
        )
        return local

    def fetch_receipt(self) -> None:
        if not self.remote:
            return
        receipt = ROOT / RECEIPT
        receipt.parent.mkdir(parents=True, exist_ok=True)
        archive = f"tar -cf - -C {CLONE} {RECEIPT}"
        self._require(
            self.runner.pipe(self._on_host(archive), ["tar", "-xf", "-", "-C", str(ROOT)]), "fetch the receipt"
        )

    def _ssh(self, command: str) -> list[str]:
        """``command`` where the machine's work happens: in a login shell in its dev container, in the checkout."""
        run = f"{self._compose} exec -T --user {CONTAINER_USER} {SERVICE} bash -lc {shlex.quote(command)}"
        return self._in_clone(run)

    def _in_clone(self, command: str) -> list[str]:
        return self._on_host(f"cd {CLONE} && {command}")

    def _on_host(self, command: str) -> list[str]:
        """``command`` on the host, in a login shell from its user's home: a plain ssh command sees no profile."""
        return ["ssh", *SSH_OPTIONS, self.config.host or "", f"bash -lc {shlex.quote(command)}"]

    @property
    def _compose(self) -> str:
        files = " ".join(f"-f {path}" for path in COMPOSE_FILES)
        return f"docker compose --project-name {shlex.quote(self.config.container)} {files}"

    def _container_up(self) -> bool:
        """Whether the dev container runs; no clone yet means it does not."""
        running = f"{self._compose} ps --status running --quiet {SERVICE} 2>/dev/null"
        code = self.runner.call(self._on_host(f'cd {CLONE} 2>/dev/null && test -n "$({running})"'))
        if code == SSH_FAILED:
            raise SystemExit(
                f">> could not reach {self.name} as {self.config.host} over SSH; is your key in the agent"
                f" (ssh-add -l), and its host key in {KNOWN_HOSTS.relative_to(ROOT)}? tools/ssh/setup-vm.sh puts both"
            )
        return code == 0

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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed machine", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the machines")
    commands.add_parser(
        "remove", help="clean up its container's runs, take the container down, and delete the clone"
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
            where = f"{config.host}:~/{CLONE}" if config.host else str(ROOT)
            inside = f"  project={config.container}" if config.host else ""
            print(f"{name:12} {where}  jobs={config.jobs}{inside}")
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
    if args.command == "gate":
        return gate(machine, args.jobs)
    if not args.recipe:
        parser.error("run needs a recipe")
    return run_recipe(machine, args.recipe)


if __name__ == "__main__":
    raise SystemExit(main())

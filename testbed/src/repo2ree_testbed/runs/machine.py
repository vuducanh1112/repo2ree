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
command runs in the clone's .envrc. It needs Git, flock, and a Docker Engine with Compose
that its SSH user may use.

A run takes a workspace on the machine, pushes the commit to it, checks it out, and starts the
recipe in the dev container detached, as that workspace's job: its command, log, and exit code
are in test-artifacts/machine-job/ of the workspace. The first workspace is the clone; a run
while every workspace has a job makes another, a clone of its own under .machine-workspaces/ of
the clone, which later runs reuse. So any number of recipes run on a machine side by side, in
one dev container, each in its own checkout. A run shows its job's log until the job ends, then
brings back what it wrote: every file under test-artifacts/, .receipts/, and logs/ of its
workspace changed since it started, whatever the recipe (runs, recordings, coverage, and
receipts, which bind a tree rather than a machine), but for experiment environment tarballs and
archives, which stay there. Ctrl-C or a dropped connection only stops the showing: the job goes
on, and running the same command again shows it again and brings its results back; any run
brings back the results of jobs that ended unseen before starting its own, as `fetch` does without
starting one. `cancel` stops a job;
`remove` takes the container down and deletes the clone with its workspaces.

What every job shares is changed only while no job runs: the dev container is rebuilt, and
garbage collected, by a run that finds the machine idle. A machine is kept bounded by steps of
their own, which the just recipes that run on a machine depend on (`just machine-gc`,
`just machine-tidy`): before a run, `gc` collects what nothing uses, so a run starts with all the
room the machine can give it; after it, `tidy` prunes the test artifacts of each idle workspace
to the newest MACHINE_KEEPS_RUNS of each tier, whose experiment environment tarballs and
archives stay only there.
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
from typing import Literal, Protocol

from pydantic import TypeAdapter, ValidationError

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.machines import MachineConfig, load_machines, machines_file
from repo2ree_testbed.stack.process import capture

# The clone, in the SSH user's home, which the dev container mounts at MOUNT.
CLONE = "repo2ree"
MOUNT = "/repo2ree"
# The clone's further workspaces, one per job beside others, each a clone of its own.
WORKSPACES = ".machine-workspaces"
CONTAINER_USER = "nixuser"
COMPOSE_FILES = ("docker-compose.dev.yml", "docker/dev/machine.compose.yml")
SERVICE = "dev"
# The Compose project of a remote machine's dev container.
PROJECT = "repo2ree-dev"
COMPOSE = f"docker compose --project-name {PROJECT} " + " ".join(f"-f {path}" for path in COMPOSE_FILES)
# A workspace's job: what it runs, its log, its process group, its exit code, and whether its
# results were brought back.
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
    # dossier already, and the machine keeps the archives, which carry every experiment environment payload.
    "! -path '*/artifacts/*/ree*.zip'",
    # The REE histories a CLI test kept: the dossier holds a copy of each already.
    "! -path '*/artifacts/kept-rees/*'",
)
# What every command on a remote machine runs in: the workspace's .envrc, as here, with the venv it syncs.
SHELL = ("direnv", "exec", ".")
# How long `gc` keeps build cache nothing used: what the dev image and the stacks' images rebuild from
# today. By age, not size: most of the cache is shared with images, and a size cap removes nothing.
CACHE_KEPT_FOR = "24h"
# How long `gc` keeps an image nothing runs: a week of rebuilds stays warm.
IMAGES_KEPT_FOR = "168h"
# The runs per tier a machine keeps once their results are here, as many as of the overview: their
# experiment environment tarballs and archives stay only there.
MACHINE_KEEPS_RUNS = 3
# How long a claimed workspace waits for its job to start (pushing, checking out, rebuilding the dev
# image) before it counts as dead: a run that died meanwhile leaves no process to ask.
CLAIM_MINUTES = 180
# How long a cancelled job has to stop its stacks before its processes are killed.
STOP_SECONDS = 60
# Taken, on the host, by whatever claims a workspace, starts a job, or changes what every job shares.
LOCKED = 'exec 9>>"$HOME/.repo2ree-machine.lock" && flock 9'

type JobState = Literal["none", "starting", "running", "ended", "fetched", "dead"]
BUSY: tuple[JobState, ...] = ("starting", "running")
_JOB_STATE: TypeAdapter[JobState] = TypeAdapter(JobState)

# In the clone, on the host: whether a workspace's job is alive in the dev container (its command
# line names the exit file it will write; the brackets keep this grep from finding itself), and
# each workspace's job as `<workspace>\t<state>\t<command>`; `busy <workspace>` lists the others busy.
_EXIT = JOB.replace("job", "jo[b]") + "/exit"
FUNCTIONS = f"""
alive() {{ {COMPOSE} exec -T {SERVICE} sh -c "grep -qs '$1/{_EXIT}' /proc/[0-9]*/cmdline" 2>/dev/null; }}
states() {{
  for dir in . {WORKSPACES}/*; do
    test -d "$dir" || continue
    if test "$dir" = .; then inside={MOUNT}; else inside="{MOUNT}/$dir"; fi
    job="$dir/{JOB}"
    if ! test -f "$job/command"; then state=none
    elif test -f "$job/fetched"; then state=fetched
    elif test -f "$job/exit"; then state=ended
    elif test -f "$job/pid"; then if alive "$inside"; then state=running; else state=dead; fi
    elif test -n "$(find "$job/command" -mmin -{CLAIM_MINUTES})"; then state=starting
    else state=dead; fi
    printf '%s\\t%s\\t%s\\n' "$dir" "$state" "$(cat "$job/command" 2>/dev/null)"
  done
}}
busy() {{ states | awk -F '\\t' -v me="$1" '$1 != me && ($2 == "starting" || $2 == "running")'; }}
""".strip()


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
class Workspace:
    """Where a job runs on a machine: the clone (``.``), or one of its further workspaces (WORKSPACES/<n>)."""

    directory: str = "."

    @property
    def host(self) -> str:
        """Its directory on the host, from the SSH user's home."""
        return CLONE if self.directory == "." else f"{CLONE}/{self.directory}"

    @property
    def inside(self) -> str:
        """Its directory in the dev container."""
        return MOUNT if self.directory == "." else f"{MOUNT}/{self.directory}"

    @property
    def ref(self) -> str:
        """The clone's ref a run pushes its commit to for this workspace."""
        return "refs/testbed/head" if self.directory == "." else f"refs/testbed/workspace-{Path(self.directory).name}"

    def path(self, relative: str) -> str:
        """``relative`` in this workspace, from the clone."""
        return relative if self.directory == "." else f"{self.directory}/{relative}"


@dataclass(frozen=True)
class Job:
    """A workspace's job: ``none``, ``starting``, ``running``, ``ended`` (results not yet here), ``fetched``, or
    ``dead``."""

    state: JobState
    command: str = ""
    workspace: Workspace = Workspace()


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
        jobs = self.jobs()
        same = next((job for job in jobs if job.command == command and job.state in ("running", "ended")), None)
        if same is not None:
            if same.state == "running":
                print(f">> {self.name} is running `{command}` already; showing it")
                if not self._show(same.workspace):
                    return INTERRUPTED
                same = self.job(same.workspace)
            return self._bring_back(same)
        for job in jobs:
            if job.state in ("ended", "dead"):
                self._bring_back(job)
        workspace = self._claim(command)
        self._ship(revision, workspace)
        self._up(workspace)
        self._start(workspace, argv)
        if not self._show(workspace):
            return INTERRUPTED
        return self._bring_back(self.job(workspace))

    def jobs(self) -> list[Job]:
        """Every workspace's job."""
        code, output = self.runner.capture(self._on_host(f"{FUNCTIONS}\ncd {CLONE} 2>/dev/null || exit 0\nstates"))
        if code == SSH_FAILED:
            raise SystemExit(
                f">> could not reach {self.name} as {self.config.host} over SSH; is your key in the agent"
                f" (ssh-add -l), and its host key in {KNOWN_HOSTS.relative_to(ROOT)}? tools/ssh/setup-vm.sh puts both"
            )
        self._require(code, "look for its jobs")
        jobs = []
        for line in filter(None, output.splitlines()):
            directory, state, command = (*line.split("\t", 2), "", "")[:3]
            try:
                known = _JOB_STATE.validate_python(state)
            except ValidationError as error:
                raise SystemExit(f">> {self.name} reports its job in {directory} as {state!r}") from error
            jobs.append(Job(known, command.strip(), Workspace(directory)))
        return jobs

    def job(self, workspace: Workspace) -> Job:
        return next((job for job in self.jobs() if job.workspace == workspace), Job("none", "", workspace))

    def fetch(self) -> int:
        """Bring back what every job that ended unseen wrote; 1 if any of them failed."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; its jobs' results are here already")
        ended = [job for job in self.jobs() if job.state in ("ended", "dead")]
        if not ended:
            print(f">> {self.name} has no ended job whose results are not here")
            return 0
        codes = []
        for job in ended:
            code = self._bring_back(job)
            print(f">> `{job.command}` ended with exit code {code}")
            codes.append(code)
        return 1 if any(codes) else 0

    def list_jobs(self) -> None:
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; its jobs are the recipes running here")
        jobs = self.jobs()
        for job in jobs:
            print(f"{job.workspace.host:36} {job.state:9} {job.command}")
        if not jobs:
            print(f">> {self.name} has no clone yet")

    def cancel(self, which: str | None = None) -> None:
        """Stop a running job, the one whose command or workspace names ``which`` if several run, and clean up the
        stacks it left: all the machine's leftovers if no other job is busy, else only those no running client
        owns."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; Ctrl-C stops its runs")
        jobs = self.jobs()
        running = [job for job in jobs if job.state == "running"]
        chosen = [job for job in running if which is None or which in job.command or which == job.workspace.directory]
        if not chosen:
            print(f">> {self.name} is running no job" + (f" matching {which!r}" if which else ""))
            return
        if len(chosen) > 1:
            listed = "\n".join(f"   {job.workspace.host}: {job.command}" for job in chosen)
            raise SystemExit(
                f">> {self.name} is running several jobs; name one by a part of its command or its workspace:\n{listed}"
            )
        [job] = chosen
        others = any(other.state in BUSY for other in jobs if other.workspace != job.workspace)
        print(f">> cancelling `{job.command}` on {self.name}")
        state = job.workspace.path(JOB)
        group = f"{job.workspace.inside}/{JOB}/pid"
        stop = (
            f"pid=$(cat {group}) && kill -TERM -- -$pid; for _ in $(seq {STOP_SECONDS}); do"
            f" kill -0 -- -$pid 2>/dev/null || exit 0; sleep 1; done; kill -KILL -- -$pid"
        )
        cleanup = (
            "python -m repo2ree_testbed workbench-cleanup --orphans"
            if others
            else "just stack-clean; just clean-workbenches"
        )
        script = " && ".join(
            [
                f"{COMPOSE} exec -T --user {CONTAINER_USER} {SERVICE} bash -c {shlex.quote(stop)}",
                f"{{ test -f {state}/exit || echo {INTERRUPTED} > {state}/exit; }}",
                f"touch {state}/fetched",
                f"{self._exec(job.workspace)} bash -lc {shlex.quote(shlex.join([*SHELL, 'bash', '-c', cleanup]))}",
            ]
        )
        self._require(self.runner.call(self._in_clone(script)), "cancel the job")

    def remove(self) -> None:
        """Clean up what runs left on the machine's Docker, take the container down, and delete the clone."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; there is nothing to remove")
        if any(job.state in BUSY for job in self.jobs()):
            raise SystemExit(f">> {self.name} is running a job; let it end, or: just machine cancel {self.name}")
        cleanup = shlex.join([*SHELL, "bash", "-c", "just stack-clean; just clean-workbenches"])
        script = "; ".join(
            [
                f"test -d {CLONE} || exit 0",
                f"cd {CLONE}",
                f"{self._exec(Workspace())} bash -lc {shlex.quote(cleanup)} 2>/dev/null",
                f"{COMPOSE} down --volumes --remove-orphans --rmi local || exit 1",
                f"cd && rm -rf {CLONE}",
            ]
        )
        self._require(self.runner.call(self._on_host(script)), "remove the container")
        print(f">> removed the dev container, its images, and the clone with its workspaces from {self.name}")

    def gc(self) -> None:
        """Bound what the machine keeps: the workspaces' generated trees, Docker's build cache, unused images.

        In the clone, the stacks runs left and every generated tree's own prune (`just prune`), which each
        further workspace runs too; in the dev container, the Nix store paths nothing roots; on the host, build
        cache unused for CACHE_KEPT_FOR and images nothing runs that are older than IMAGES_KEPT_FOR. The running
        dev container and its image stay, and so do the bundle stores, which the testbed prunes itself.

        Here, a run prunes test-artifacts itself; there, a machine with a job busy is left alone, and no job
        starts while it collects.
        """
        if not self.remote:
            print(f">> {self.name} is this checkout; `just prune` bounds it")
            return
        # A workspace at a commit before `just prune` existed skips it rather than failing on it.
        prune = "just --show prune >/dev/null 2>&1 && just prune"
        clone = shlex.quote(shlex.join([*SHELL, "bash", "-c", f"just stack-clean; just clean-workbenches; {prune}"]))
        further = shlex.quote(shlex.join([*SHELL, "bash", "-c", prune]))
        workdir = f'"{MOUNT}/$dir"'
        script = "\n".join(
            [
                FUNCTIONS,
                LOCKED,
                "df -h / | tail -n 1",
                f"if test -d {CLONE}; then",
                f"  cd {CLONE}",
                '  busy=$(busy "" | cut -f 3)',
                '  if test -n "$busy"; then',
                f'    echo ">> {self.name} is running jobs; collecting nothing while they run:"; echo "$busy"; exit 0',
                "  fi",
                f"  {self._exec(Workspace())} bash -lc {clone}",
                f"  for dir in {WORKSPACES}/*; do",
                '    test -d "$dir/.git" || continue',
                f"    {COMPOSE} exec -T --user {CONTAINER_USER} --workdir {workdir} {SERVICE} bash -lc {further}",
                "  done",
                # The dev container's Nix store: what no root (its dev shell, a bundle's out-link) holds.
                f"  {self._exec(Workspace())} nix-collect-garbage --quiet > /dev/null",
                "  cd",
                "fi",
                f"docker builder prune -a -f --filter until={CACHE_KEPT_FOR} > /dev/null",
                f"docker image prune -a -f --filter until={IMAGES_KEPT_FOR} > /dev/null",
                "docker system df",
                "df -h / | tail -n 1",
            ]
        )
        self._require(self.runner.call(self._on_host(script)), "collect garbage")

    def tidy(self) -> None:
        """Prune each workspace's test artifacts to the newest runs per tier, once its last job's results are here.

        Here, a run prunes test-artifacts itself; there, a workspace whose job is busy or not yet brought back
        keeps all.
        """
        if not self.remote:
            return
        prune = shlex.join(
            [
                *SHELL,
                *("python", "-m", "repo2ree_testbed", "prune"),
                *("--keep-runs", str(MACHINE_KEEPS_RUNS), "--keep-suite", str(MACHINE_KEEPS_RUNS)),
            ]
        )
        for job in self.jobs():
            if job.state not in ("none", "fetched"):
                print(
                    f">> {self.name} has `{job.command}` {job.state}, its results not here yet; pruning nothing of it"
                )
                continue
            command = f"{self._exec(job.workspace)} bash -lc {shlex.quote(prune)}"
            self._require(self.runner.call(self._in_clone(command)), "prune its runs")

    def _claim(self, command: str) -> Workspace:
        """Take the first workspace with no job busy or unseen for ``command``, or make one; record the job in it."""
        free = "states | awk -F '\\t' '$2 == \"none\" || $2 == \"fetched\" {print $1; exit}'"
        job = f'"$dir/{JOB}"'
        script = "\n".join(
            [
                FUNCTIONS,
                f"test -d {CLONE}/.git || git init -q {CLONE}",
                f"cd {CLONE} && {LOCKED} || exit 1",
                f"dir=$({free})",
                f'if test -z "$dir"; then n=1; while test -e {WORKSPACES}/$n; do n=$((n + 1)); done',
                f"  dir={WORKSPACES}/$n; fi",
                f"rm -rf {job} && mkdir -p {job} && printf '%s\\n' {shlex.quote(command)} > {job}/command || exit 1",
                'echo "$dir"',
            ]
        )
        code, output = self.runner.capture(self._on_host(script))
        self._require(code, "claim a workspace")
        workspace = Workspace(output.strip().splitlines()[-1])
        if workspace.directory != ".":
            print(f">> {self.name} has other jobs; this one runs in {workspace.host}", flush=True)
        return workspace

    def _ship(self, revision: str, workspace: Workspace) -> None:
        """Put ``revision`` in the workspace, checked out clean."""
        ssh = shlex.join(["ssh", *SSH_OPTIONS])
        destination = f"{self.config.host}:{CLONE}"
        push = ["git", "-c", f"core.sshCommand={ssh}", "push", "-q", "--force", destination]
        self._require(self.runner.call([*push, f"{revision}:{workspace.ref}"]), "push the commit")
        checkout = f"git checkout -q --detach --force {revision} && git clean -fdq"
        if workspace.directory != ".":
            # From the clone, whose objects it shares the way any local clone does.
            fetch = f"git fetch -q --no-tags ../.. {workspace.ref}"
            checkout = f"cd {workspace.directory} && {{ test -d .git || git init -q; }} && {fetch} && {checkout}"
        self._require(self.runner.call(self._in_clone(checkout)), "check the commit out")

    def _up(self, workspace: Workspace) -> None:
        """Bring the dev container up and wait until its user is set up; rebuilt (Compose rebuilds only what
        changed) only while no other job is busy, which a rebuilt container would stop."""
        script = "\n".join(
            [
                FUNCTIONS,
                f"cd {CLONE} && {LOCKED} || exit 1",
                f'if test -n "$(busy {shlex.quote(workspace.directory)})"; then',
                f"  echo '>> {self.name} has other jobs: its dev container stays as it is'",
                f"  {COMPOSE} up -d --no-recreate --wait",
                "else",
                f"  {COMPOSE} up -d --build --quiet-pull --wait",
                "fi",
            ]
        )
        self._require(self.runner.call(self._on_host(script)), "bring the dev container up")

    def _start(self, workspace: Workspace, argv: Sequence[str]) -> None:
        """Start ``argv`` in the dev container as the workspace's job, detached from this connection, in a
        process group of its own, which `cancel` stops.

        The job knows the machine by name, so what it records (logs/just/) says where it ran.
        """
        job = f"{workspace.inside}/{JOB}"
        machine = f"REPO2REE_MACHINE={shlex.quote(self.name)}"
        body = f"echo $$ > {job}/pid; {machine} {shlex.join([*SHELL, *argv])} > {job}/log 2>&1; echo $? > {job}/exit"
        script = " && ".join(
            [
                LOCKED,
                f": > {workspace.path(JOB)}/log",
                f"{self._exec(workspace, detached=True)} setsid bash -lc {shlex.quote(body)}",
            ]
        )
        self._require(self.runner.call(self._in_clone(script)), "start the job")

    def _show(self, workspace: Workspace) -> bool:
        """Show the job's log until it ends; False if Ctrl-C or a lost connection stopped the showing first."""
        job = workspace.path(JOB)
        script = "\n".join(
            [
                FUNCTIONS,
                f"cd {CLONE} || exit 1",
                f"tail -n +1 -f {job}/log & shown=$!",
                f"while ! test -f {job}/exit && alive {workspace.inside}; do sleep 5; done",
                "sleep 1; kill $shown",
            ]
        )
        again = (
            f"run it again to show the job and bring its results back, just machine fetch {self.name} once it"
            f" ended, or: just machine cancel {self.name}"
        )
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
        workspace = job.workspace
        read, exit_line = self.runner.capture(self._in(workspace, f"cat {JOB}/exit 2>/dev/null; echo"))
        self._require(read, "read the job's exit code")
        code = int(exit_line) if exit_line.strip() else None
        if self.runner.call(self._in(workspace, f"mkdir {JOB}/fetching 2>/dev/null")) != 0:
            print(f">> another run is already bringing back `{job.command}` from {self.name}; not copying it twice")
            return 1 if code is None else code
        read, listed = self.runner.capture(self._in(workspace, self._written))
        self._require(read, "list what the job wrote")
        written = [line for line in listed.splitlines() if line]
        if written:
            archive = self._in(workspace, f"{self._written} | tar -cf - -T -")
            self._require(self.runner.pipe(archive, ["tar", "-xf", "-", "-C", str(ROOT)]), "bring back its results")
            for result in _results(written):
                print(f">> from {self.name}: {result}")
        if code is None:
            print(f">> `{job.command}` died on {self.name} without an exit code")
        self._require(self.runner.call(self._in(workspace, f"touch {JOB}/fetched")), "record the job fetched")
        return 1 if code is None else code

    @property
    def _written(self) -> str:
        """Lists the files, and the empty folders, the job wrote under test-artifacts/, .receipts/, and logs/ since it
        started (wrote its process group)."""
        # An empty folder comes back too: a dossier can list a source that is rightly empty.
        kinds = r"\( -type f -o -type d -empty \)"
        tests = " ".join([kinds, f"-cnewer {JOB}/pid", f"! -path '{JOB}/*'", *SLIM_EXCLUDES])
        return f"{{ find test-artifacts .receipts logs {tests} 2>/dev/null || true; }}"

    def _exec(self, workspace: Workspace, *, detached: bool = False) -> str:
        mode = "-d" if detached else "-T"
        return f"{COMPOSE} exec {mode} --user {CONTAINER_USER} --workdir {workspace.inside} {SERVICE}"

    def _in(self, workspace: Workspace, command: str) -> list[str]:
        return self._on_host(f"cd {workspace.host} && {command}")

    def _in_clone(self, command: str) -> list[str]:
        return self._in(Workspace(), command)

    def _on_host(self, command: str) -> list[str]:
        """``command`` on the host, in a login shell from its user's home: a plain ssh command sees no profile."""
        return ["ssh", *SSH_OPTIONS, self.config.host or "", f"bash -lc {shlex.quote(command)}"]

    def fetch_archives(self) -> int:
        """Bring the machine's image archive sets here, the newest of its workspaces' for each platform, replacing
        this checkout's set for each platform it has."""
        if not self.remote:
            raise SystemExit(f">> {self.name} is this checkout; its archives are in {ARCHIVES} already")
        listing = (
            f"for dir in {ARCHIVES}/* {WORKSPACES}/*/{ARCHIVES}/*; do"
            f' test -d "$dir" && printf \'%s\\t%s\\n\' "$(stat -c %Y "$dir")" "$dir"; done; true'
        )
        listed, lines = self.runner.capture(self._in_clone(listing))
        self._require(listed, "list its image archives")
        newest: dict[str, tuple[int, Path]] = {}
        for line in filter(None, lines.splitlines()):
            stamp, _, directory = line.partition("\t")
            found = Path(directory)
            if not found.name.startswith(".") and int(stamp) >= newest.get(found.name, (-1, found))[0]:
                newest[found.name] = (int(stamp), found)
        if not newest:
            print(f">> {self.name} has no image archives: run just archive-images there after its publish gate")
            return 1
        (ROOT / ARCHIVES).mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".fetching-", dir=ROOT / ARCHIVES))
        try:
            for platform, (_, found) in sorted(newest.items()):
                archive = self._in_clone(f"tar -cf - -C {found.parent} {platform}")
                self._require(
                    self.runner.pipe(archive, ["tar", "-xf", "-", "-C", str(staging)]), "bring back its archives"
                )
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
    Nothing but the machine's ref for its workspace reaches it, and a receipt it earns binds
    its tree, which only a commit of exactly that content can claim. A clean tree is HEAD. It is
    dated as HEAD is, so the same working tree is the same commit, and running it again finds its job.
    """
    if not capture(["git", "status", "--porcelain"]):
        return capture(["git", "rev-parse", "HEAD"])
    with tempfile.TemporaryDirectory() as scratch:
        index = {**os.environ, "GIT_INDEX_FILE": str(Path(scratch) / "index")}
        capture(["git", "read-tree", "HEAD"], env=index, check=True)
        capture(["git", "add", "-A"], env=index, check=True)
        tree = capture(["git", "write-tree"], env=index, check=True)
    author = {} if capture(["git", "config", "user.email"]) else WIP_IDENTITY
    date = capture(["git", "show", "-s", "--format=%cd", "--date=raw", "HEAD"], check=True)
    dated = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    message = "work in progress, run on a machine"
    return capture(
        ["git", "commit-tree", tree, "-p", "HEAD", "-m", message], env={**os.environ, **author, **dated}, check=True
    )


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
    commands.add_parser("jobs", help="list each workspace's job there").add_argument("machine")
    commands.add_parser("fetch", help="bring back what the jobs that ended there unseen wrote").add_argument("machine")
    cancelling = commands.add_parser("cancel", help="stop a job running there")
    cancelling.add_argument("machine")
    cancelling.add_argument("job", nargs="?", help="a part of its command, or its workspace, if several run")
    commands.add_parser(
        "gc", help="prune the clone's generated trees, Docker's build cache, and unused images there"
    ).add_argument("machine")
    commands.add_parser(
        "tidy",
        help=f"prune its test artifacts to the newest {MACHINE_KEEPS_RUNS} runs per tier once its results are here",
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
    if args.command == "fetch":
        return machine.fetch()
    if args.command == "jobs":
        machine.list_jobs()
        return 0
    if args.command == "cancel":
        machine.cancel(args.job)
        return 0
    if args.command == "gc":
        machine.gc()
        return 0
    if args.command == "tidy":
        machine.tidy()
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

"""``python -m repo2ree_testbed target``: run the gate or a tier on a machine, here or over SSH.

A target is where the stacks run. ``local`` is this checkout; any other is an SSH
machine named in the targets file (``$REPO2REE_TARGETS``, by default
``~/.config/repo2ree/targets.toml``), since hosts and paths are a developer's own:

    [targets.vm]
    host = "vm"            # an ssh destination: an alias, or user@host
    path = "repo2ree"      # the clone on the target, relative to its home or absolute
    jobs = 6               # stacks side by side per tier
    # shell = ["nix", "develop", "--command"]   what every command runs inside
    # fetch = "slim"       # or "full": "slim" leaves runtime tarballs and archives behind

A remote target gets HEAD pushed to it and checked out clean, runs the recipe in
its dev shell, and sends back every per-test run the recipe reported; the gate
also sends back its receipt, which binds a tree rather than a machine, so it holds
here as it did there. The target needs git and Nix; the repository needs to be
committed, since only a commit can be shipped.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.stack.process import capture
from repo2ree_testbed.targets import Target, load_targets, targets_file

RUN_LINE = ">> per-test run: "
RECEIPT = ".receipts/assurance-gate.json"
# What a slim fetch leaves on the target: the bulk of a run, and nothing a verdict or a page reads.
SLIM_EXCLUDES = ("*.tar", "*.tar.gz", "*.tgz", "*/artifacts/archives")


class Runner(Protocol):
    def call(self, argv: Sequence[str]) -> int: ...

    def stream(self, argv: Sequence[str]) -> tuple[int, list[str]]:
        """Run ``argv`` showing its output as it comes; its exit code, and every line it printed."""
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
                printed.append(line.rstrip("\n"))
        return proc.returncode, printed

    def pipe(self, producer: Sequence[str], consumer: Sequence[str]) -> int:
        with subprocess.Popen(list(producer), cwd=ROOT, stdout=subprocess.PIPE) as source:
            received = subprocess.run(list(consumer), cwd=ROOT, stdin=source.stdout, check=False).returncode
        return source.returncode or received


@dataclass
class Machine:
    """One target, reached the way its kind is reached; the same verbs either way."""

    name: str
    target: Target
    runner: Runner = field(default_factory=Processes)

    @property
    def remote(self) -> bool:
        return self.target.host is not None

    def ship(self, revision: str) -> None:
        """Put ``revision`` on the target, checked out clean (a local target already has it)."""
        if not self.remote:
            return
        path = shlex.quote(self.target.path)
        self._require(self.runner.call(self._ssh(f"test -d {path}/.git || git init -q {path}")), "prepare the clone")
        destination = f"{self.target.host}:{self.target.path}"
        self._require(
            self.runner.call(["git", "push", "-q", "--force", destination, f"{revision}:refs/testbed/head"]),
            "push the commit",
        )
        self._require(
            self.runner.call(self._ssh(f"cd {path} && git checkout -q --detach --force {revision} && git clean -fdq")),
            "check the commit out",
        )

    def run(self, argv: Sequence[str]) -> tuple[int, list[Path]]:
        """Run ``argv`` in the target's checkout; its exit code, and the per-test runs it reported."""
        command = [*self.target.shell, *argv]
        if self.remote:
            line = " ".join(shlex.quote(part) for part in command)
            code, printed = self.runner.stream(self._ssh(f"cd {shlex.quote(self.target.path)} && {line}"))
        else:
            code, printed = self.runner.stream(command)
        runs = [Path(line.removeprefix(RUN_LINE).strip()) for line in printed if line.startswith(RUN_LINE)]
        return code, runs

    def fetch_run(self, run: Path) -> Path:
        """Bring a run the target wrote into this checkout's test-artifacts; where it now is."""
        if not self.remote:
            return run
        local = ROOT / "test-artifacts" / _after_test_artifacts(run)
        local.parent.mkdir(parents=True, exist_ok=True)
        excludes = [f"--exclude={pattern}" for pattern in SLIM_EXCLUDES] if self.target.fetch == "slim" else []
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
        archive = f"tar -cf - -C {shlex.quote(self.target.path)} {RECEIPT}"
        self._require(self.runner.pipe(self._ssh(archive), ["tar", "-xf", "-", "-C", str(ROOT)]), "fetch the receipt")

    def _ssh(self, command: str) -> list[str]:
        """``command`` on the target, in a login shell: a plain ssh command sees no profile, so often no Nix."""
        return ["ssh", self.target.host or "", f"bash -lc {shlex.quote(command)}"]

    def _require(self, code: int, what: str) -> None:
        if code != 0:
            raise SystemExit(f">> could not {what} on {self.name} (exit {code})")


def _after_test_artifacts(run: Path) -> Path:
    """A run's path below test-artifacts/, wherever the target keeps its checkout."""
    parts = run.parts
    if "test-artifacts" not in parts:
        raise SystemExit(f">> {run} is not under a test-artifacts directory")
    return Path(*parts[len(parts) - parts[::-1].index("test-artifacts") :])


def committed_head() -> str:
    """HEAD, refusing uncommitted changes: what a target runs is a commit, so nothing else may count."""
    if capture(["git", "status", "--porcelain"]):
        raise SystemExit(">> the working tree is not clean; commit first, since a target runs a commit")
    return capture(["git", "rev-parse", "HEAD"])


def gate(machine: Machine, jobs: int | None) -> int:
    machine.ship(committed_head())
    code, runs = machine.run(["just", "assurance-gate", str(jobs or machine.target.jobs)])
    for run in runs:
        print(f">> run from {machine.name}: {machine.fetch_run(run).relative_to(ROOT)}")
    if code == 0:
        machine.fetch_receipt()
        print(f">> assurance-gate receipt from {machine.name}: {RECEIPT}")
    return code


def run_recipe(machine: Machine, recipe: Sequence[str]) -> int:
    if machine.remote:
        machine.ship(committed_head())
    code, runs = machine.run(["just", *recipe])
    for run in runs:
        print(f">> run from {machine.name}: {machine.fetch_run(run).relative_to(ROOT)}")
    return code


def prepare(machine: Machine) -> int:
    machine.ship(committed_head())
    code, _ = machine.run(["just", "build-e2e-bundles"])
    return code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed target", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the targets")
    commands.add_parser("prepare", help="ship HEAD and build the bundles, so the first run starts warm").add_argument(
        "target"
    )
    gating = commands.add_parser("gate", help="run the assurance gate there and bring its receipt and runs back")
    gating.add_argument("target")
    gating.add_argument("--jobs", type=int, help="stacks side by side per tier (default: the target's)")
    running = commands.add_parser("run", help="run a just recipe there and bring back the per-test runs it made")
    running.add_argument("target")
    running.add_argument("recipe", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    path = targets_file()
    targets = load_targets(path)
    if args.command == "list":
        for name, target in targets.items():
            where = f"{target.host}:{target.path}" if target.host else target.path
            print(f"{name:12} {where}  jobs={target.jobs}")
        return 0
    if args.target not in targets:
        raise SystemExit(f">> no target {args.target!r}; known: {', '.join(targets)} (from {path})")
    machine = Machine(args.target, targets[args.target])
    if args.command == "prepare":
        return prepare(machine)
    if args.command == "gate":
        return gate(machine, args.jobs)
    if not args.recipe:
        parser.error("run needs a recipe")
    return run_recipe(machine, args.recipe)


if __name__ == "__main__":
    raise SystemExit(main())

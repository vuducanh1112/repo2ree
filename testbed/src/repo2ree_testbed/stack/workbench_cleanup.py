"""Remove Docker resources left by workbench runs.

A stack removes what it started when it stops. A stack that dies first, its run interrupted or its dev
container restarted, leaves its machines running on the engine: they are ``docker run`` containers, and
killing the client that started one does not stop it. They carry their stack's label, and a machine whose
client is no longer running here is one no stack will stop.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from repo2ree_testbed.stack.process import lines

ANONYMOUS_VOLUME = re.compile(r"[0-9a-f]{64}")
OWNER_LABEL = "repo2ree.resource-owner"
PROCESSES = Path("/proc")


def workbench_containers(owner: str | None) -> list[str]:
    """The containers a run left (its jobs carry its label), or every job and bench container."""
    if owner:
        return sorted(set(lines(["docker", "ps", "-aq", "--filter", f"label=repo2ree.resource-owner={owner}"])))
    return sorted(
        {
            name
            for prefix in ("repo2ree-job-", "repo2ree-wb-")
            for name in lines(["docker", "ps", "-aq", "--filter", f"name=^{prefix}"])
        }
    )


def save_bench_logs(owner: str, directory: Path) -> list[Path]:
    """Keep what each container of the run still alive at teardown printed.

    What a job container prints exists only in ``docker logs``, which the cleanup
    that follows deletes with the container.
    """
    saved = []
    listing = ["docker", "ps", "-a", "--format", "{{.Names}}", "--filter", f"label=repo2ree.resource-owner={owner}"]
    for name in sorted(set(lines(listing))):
        result = subprocess.run(["docker", "logs", "--timestamps", name], check=False, capture_output=True)
        path = directory / f"bench-{name.removeprefix('repo2ree-wb-')}.log"
        directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(result.stdout + result.stderr)
        saved.append(path)
    return saved


def running_commands(processes: Path = PROCESSES) -> list[tuple[str, ...]]:
    """The argv of every process running here."""
    commands = []
    for cmdline in processes.glob("[0-9]*/cmdline"):
        try:
            raw = cmdline.read_bytes()
        except OSError:
            continue
        if raw:
            commands.append(tuple(raw.decode(errors="replace").rstrip("\0").split("\0")))
    return commands


def started_here(container: str, commands: Iterable[tuple[str, ...]]) -> bool:
    """Whether a ``docker run --name <container>`` that started it is still running here."""
    return any(
        "docker" in Path(argv[0]).name and "run" in argv and (*argv, "")[argv.index("--name") + 1] == container
        for argv in commands
        if "--name" in argv
    )


def orphaned_owners(commands: Iterable[tuple[str, ...]] | None = None) -> list[str]:
    """The stacks whose machines (the containers ``<owner>-<n>`` a stack starts) are still on the engine with none
    of their clients running here."""
    machines: dict[str, list[str]] = {}
    listing = ["docker", "ps", "-a", "--filter", f"label={OWNER_LABEL}", "--format", "{{.Names}}\t{{.Labels}}"]
    for line in lines(listing):
        name, _, labels = line.partition("\t")
        owner = dict(label.partition("=")[::2] for label in labels.split(",")).get(OWNER_LABEL, "")
        if owner and re.fullmatch(rf"{re.escape(owner)}-[0-9]+", name):
            machines.setdefault(owner, []).append(name)
    running = running_commands() if commands is None else list(commands)
    return sorted(owner for owner, names in machines.items() if not any(started_here(name, running) for name in names))


def owned_volumes(owner: str) -> list[str]:
    return sorted(set(lines(["docker", "volume", "ls", "-q", "--filter", f"label=repo2ree.resource-owner={owner}"])))


def global_volumes() -> list[str]:
    """The anonymous volumes no container uses any more."""
    return sorted(
        name
        for name in lines(["docker", "volume", "ls", "-q", "--filter", "dangling=true"])
        if ANONYMOUS_VOLUME.fullmatch(name)
    )


def remove(kind: str, values: list[str], owner: str | None) -> None:
    if not values:
        return
    print(f">> removing leftover workbench {kind}{f' for {owner}' if owner else ''}")
    if kind == "containers":
        subprocess.run(["docker", "rm", "-f", "-v", *values], check=False, stdout=subprocess.DEVNULL)
    else:
        subprocess.run(["docker", "volume", "rm", *values], check=False, stdout=subprocess.DEVNULL)


def cleanup(owner: str | None) -> None:
    """Remove what the stack ``owner`` left, or, with no owner, what every run left: job and bench containers,
    the machines of stacks no longer running, and the volumes nothing uses any more."""
    if owner:
        remove("containers", workbench_containers(owner), owner)
        remove("volumes", owned_volumes(owner), owner)
        return
    remove("containers", workbench_containers(None), None)
    for orphan in orphaned_owners():
        remove("containers", workbench_containers(orphan), orphan)
        remove("volumes", owned_volumes(orphan), orphan)
    remove("volumes", global_volumes(), None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner")
    args = parser.parse_args()
    try:
        cleanup(args.owner)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

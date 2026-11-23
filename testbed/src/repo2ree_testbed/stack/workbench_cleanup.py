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
    return any(
        "docker" in Path(argv[0]).name and "run" in argv and (*argv, "")[argv.index("--name") + 1] == container
        for argv in commands
        if "--name" in argv
    )


def orphaned_owners(commands: Iterable[tuple[str, ...]] | None = None) -> list[str]:
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
    if owner:
        remove("containers", workbench_containers(owner), owner)
        remove("volumes", owned_volumes(owner), owner)
        return
    remove("containers", workbench_containers(None), None)
    cleanup_orphans()
    remove("volumes", global_volumes(), None)


def cleanup_orphans() -> None:
    for orphan in orphaned_owners():
        remove("containers", workbench_containers(orphan), orphan)
        remove("volumes", owned_volumes(orphan), orphan)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner")
    parser.add_argument("--orphans", action="store_true", help="only what stacks no longer running left")
    args = parser.parse_args()
    try:
        if args.orphans:
            cleanup_orphans()
        else:
            cleanup(args.owner)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

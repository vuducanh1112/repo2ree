"""Remove Docker resources left by workbench runs."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from repo2ree_testbed.stack.process import lines

ANONYMOUS_VOLUME = re.compile(r"[0-9a-f]{64}")


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
    remove("containers", workbench_containers(owner), owner)
    remove("volumes", owned_volumes(owner) if owner else global_volumes(), owner)


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

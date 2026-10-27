"""Remove Docker resources left by workbench runs."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.stack.process import capture, lines

ANONYMOUS_VOLUME = re.compile(r"[0-9a-f]{64}")


class Volume(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    CreatedAt: dt.datetime


def live_store_volume() -> str:
    exec_bundle = Path(os.getenv("REPO2REE_EXEC_BUNDLE", str(ROOT / "dist/bundles/exec")))
    tools_bundle = Path(os.getenv("REPO2REE_TOOLS_BUNDLE", str(ROOT / "dist/bundles/tools")))
    if not exec_bundle.is_dir():
        return ""
    tools = str(tools_bundle) if tools_bundle.is_dir() else ""
    return capture(
        [
            *("uv", "run", "--package", "repo2ree-provider-docker", "python", "-c"),
            (
                "import sys; from repo2ree_provider_docker.injection import load_injection_bundle; "
                "bundle = load_injection_bundle(sys.argv[1], sys.argv[2] or None); "
                'print(bundle.volume_name if bundle else "")'
            ),
            str(exec_bundle),
            tools,
        ]
    )


# Unused bundle stores kept besides the current checkout's: one per recent bundle
# (about 600 MB each), so switching back to a recent commit copies nothing.
KEEP_STORES = 2


def stale_store_volumes(keep: str, keep_newest: int) -> list[str]:
    """Unused bundle stores beyond the newest ``keep_newest``; ``keep`` (the checkout's own) is never one."""
    unused: list[tuple[dt.datetime, str]] = []
    for name in lines(
        ["docker", "volume", "ls", "-q", "--filter", "dangling=true", "--filter", "name=^repo2ree-store-"]
    ):
        if name == keep:
            continue
        output = capture(["docker", "volume", "inspect", name, "--format", "{{json .}}"])
        try:
            unused.append((Volume.model_validate_json(output).CreatedAt, name))
        except ValidationError:
            continue
    unused.sort(reverse=True)
    return sorted(name for _, name in unused[keep_newest:])


def workbench_containers(owner: str | None) -> list[str]:
    resource_filter = f"label=repo2ree.resource-owner={owner}" if owner else "name=^repo2ree-wb-"
    return sorted(set(lines(["docker", "ps", "-aq", "--filter", resource_filter])))


def owned_volumes(owner: str) -> list[str]:
    return sorted(set(lines(["docker", "volume", "ls", "-q", "--filter", f"label=repo2ree.resource-owner={owner}"])))


def global_volumes(include_store: bool) -> list[str]:
    prefixes = ["repo2ree-ree-", "repo2ree-dind-"]
    if include_store:
        prefixes.append("repo2ree-store-")
    volumes = {
        name for prefix in prefixes for name in lines(["docker", "volume", "ls", "-q", "--filter", f"name=^{prefix}"])
    }
    volumes.update(
        name
        for name in lines(["docker", "volume", "ls", "-q", "--filter", "dangling=true"])
        if ANONYMOUS_VOLUME.fullmatch(name)
    )
    return sorted(volumes)


def remove(kind: str, values: list[str], owner: str | None) -> None:
    if not values:
        return
    print(f">> removing leftover workbench {kind}{f' for {owner}' if owner else ''}")
    if kind == "containers":
        subprocess.run(["docker", "rm", "-f", "-v", *values], check=False, stdout=subprocess.DEVNULL)
    else:
        subprocess.run(["docker", "volume", "rm", *values], check=False, stdout=subprocess.DEVNULL)


def cleanup(owner: str | None, store: bool, store_gc: int | None) -> None:
    remove("containers", workbench_containers(owner), owner)
    volumes = owned_volumes(owner) if owner else global_volumes(store)
    remove("volumes", volumes, owner)
    if store_gc is not None:
        keep = live_store_volume()
        stale = stale_store_volumes(keep, store_gc)
        if stale:
            suffix = f" besides {keep}" if keep else ""
            print(f">> removing {len(stale)} bundle store volume(s), keeping the newest {store_gc} unused{suffix}")
            subprocess.run(["docker", "volume", "rm", *stale], check=False, stdout=subprocess.DEVNULL)


def nonnegative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("the number of stores kept must be nonnegative")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument("--owner")
    choices.add_argument("--store", action="store_true")
    choices.add_argument("--store-gc", nargs="?", type=nonnegative, const=KEEP_STORES)
    args = parser.parse_args()
    try:
        cleanup(args.owner, args.store, args.store_gc)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

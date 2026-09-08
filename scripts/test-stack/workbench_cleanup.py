#!/usr/bin/env python3
"""Remove Docker resources left by workbench runs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANONYMOUS_VOLUME = re.compile(r"[0-9a-f]{64}")


def capture(*args: str, check: bool = False) -> str:
    result = subprocess.run(args, check=check, capture_output=True, text=True)
    return result.stdout.strip()


def lines(*args: str) -> list[str]:
    return [line for line in capture(*args).splitlines() if line]


def live_store_volume() -> str:
    exec_bundle = Path(os.getenv("REPO2REE_EXEC_BUNDLE", str(ROOT / "dist/bundles/exec")))
    tools_bundle = Path(os.getenv("REPO2REE_TOOLS_BUNDLE", str(ROOT / "dist/bundles/tools")))
    if not exec_bundle.is_dir():
        return ""
    tools = str(tools_bundle) if tools_bundle.is_dir() else ""
    return capture(
        "uv",
        "run",
        "--package",
        "repo2ree-provider-docker",
        "python",
        "-c",
        "import sys; from repo2ree_provider_docker.injection import load_injection_bundle; "
        "bundle = load_injection_bundle(sys.argv[1], sys.argv[2] or None); "
        'print(bundle.volume_name if bundle else "")',
        str(exec_bundle),
        tools,
    )


def stale_store_volumes(max_age_days: float, keep: str) -> list[str]:
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=max_age_days)
    stale: list[str] = []
    for name in lines("docker", "volume", "ls", "-q", "--filter", "dangling=true", "--filter", "name=^repo2ree-store-"):
        if name == keep:
            continue
        output = capture("docker", "volume", "inspect", name, "--format", "{{json .}}")
        if not output:
            continue
        created = dt.datetime.fromisoformat(json.loads(output)["CreatedAt"])
        if created < cutoff:
            stale.append(name)
    return sorted(set(stale))


def workbench_containers(owner: str | None) -> list[str]:
    resource_filter = f"label=repo2ree.resource-owner={owner}" if owner else "name=^repo2ree-wb-"
    return sorted(set(lines("docker", "ps", "-aq", "--filter", resource_filter)))


def owned_volumes(owner: str) -> list[str]:
    return sorted(set(lines("docker", "volume", "ls", "-q", "--filter", f"label=repo2ree.resource-owner={owner}")))


def global_volumes(include_store: bool) -> list[str]:
    prefixes = ["repo2ree-ree-", "repo2ree-dind-"]
    if include_store:
        prefixes.append("repo2ree-store-")
    volumes = {
        name for prefix in prefixes for name in lines("docker", "volume", "ls", "-q", "--filter", f"name=^{prefix}")
    }
    volumes.update(
        name
        for name in lines("docker", "volume", "ls", "-q", "--filter", "dangling=true")
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


def cleanup(owner: str | None, store: bool, store_gc: float | None) -> None:
    remove("containers", workbench_containers(owner), owner)
    volumes = owned_volumes(owner) if owner else global_volumes(store)
    remove("volumes", volumes, owner)
    if store_gc is not None:
        keep = live_store_volume()
        stale = stale_store_volumes(store_gc, keep)
        if stale:
            suffix = f" (keeping {keep})" if keep else ""
            print(f">> removing bundle store volumes unused for {store_gc:g}d{suffix}")
            subprocess.run(["docker", "volume", "rm", *stale], check=False, stdout=subprocess.DEVNULL)


def nonnegative(value: str) -> float:
    parsed = float(value)
    if not (parsed >= 0 and parsed < float("inf")):
        raise argparse.ArgumentTypeError("days must be a nonnegative finite number")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument("--owner")
    choices.add_argument("--store", action="store_true")
    choices.add_argument("--store-gc", nargs="?", type=nonnegative, const=14.0)
    args = parser.parse_args()
    try:
        cleanup(args.owner, args.store, args.store_gc)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

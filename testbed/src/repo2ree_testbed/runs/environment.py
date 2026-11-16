"""``python -m repo2ree_testbed environment <name>``: a machine starts, runs what it offers, and leaves nothing."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import uuid
from collections.abc import Sequence

from repo2ree_testbed.stack.environments import ENVIRONMENTS, Environment, machine_command
from repo2ree_testbed.stack.services import workbench_host
from repo2ree_testbed.stack.store_images import PYTHON_SLIM_IMAGE
from repo2ree_testbed.stack.workbench_cleanup import cleanup, owned_volumes, workbench_containers

SETUP_SECONDS = 1200


def probe(environment: Environment) -> str:
    """What must work on the machine: the workbench it is installed with, and a container where it has an engine."""
    steps = ["repo2ree-workbench --help >/dev/null"]
    if environment.engine:
        steps.append(shlex.join([environment.engine, "run", "--rm", PYTHON_SLIM_IMAGE, "python", "--version"]))
    return " && ".join(steps)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed environment")
    parser.add_argument("name", choices=sorted(ENVIRONMENTS))
    args = parser.parse_args(argv)
    environment = ENVIRONMENTS[args.name]
    owner = f"environment-check-{args.name}-{uuid.uuid4().hex[:12]}"
    command = machine_command(
        environment,
        {},
        ["sh", "-c", probe(environment)],
        container=owner,
        owner=owner,
        network=workbench_host()[1],
        mounts=(),
    )
    try:
        status = subprocess.run(command, check=False, timeout=SETUP_SECONDS).returncode
    except subprocess.TimeoutExpired:
        print(f">> {args.name} did not finish within {SETUP_SECONDS}s", file=sys.stderr)
        status = 1
    print(f">> {args.name}: setup {'ok' if status == 0 else f'FAILED ({status})'}")
    cleanup(owner)
    left = [*workbench_containers(owner), *owned_volumes(owner)]
    print(f">> {args.name}: cleanup {'ok' if not left else f'LEFT {left}'}")
    return 1 if status != 0 or left else 0


if __name__ == "__main__":
    raise SystemExit(main())

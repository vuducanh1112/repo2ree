#!/usr/bin/env python3
"""Record and verify the local image set exercised by the publish gate."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

IMAGES = ("repo2ree-gui", "repo2ree-backend", "repo2ree-provider-docker")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True)
class GateReceipt:
    revision: str
    tree: str
    images: dict[str, str]


def capture(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def image_id(image: str) -> str:
    value = capture("docker", "image", "inspect", "--format", "{{.Id}}", image)
    if not DIGEST.fullmatch(value):
        raise RuntimeError(f"invalid local image ID for {image}: {value}")
    return value


def parse_receipt(path: Path) -> GateReceipt:
    values: dict[str, str] = {}
    images: dict[str, str] = {}
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) == 2 and fields[0] in {"revision", "tree"}:
            if fields[0] in values:
                raise RuntimeError(f"duplicate {fields[0]} in {path}")
            values[fields[0]] = fields[1]
        elif len(fields) == 3 and fields[0] == "image" and fields[1] in IMAGES:
            if fields[1] in images:
                raise RuntimeError(f"duplicate image {fields[1]} in {path}")
            images[fields[1]] = fields[2]
        else:
            raise RuntimeError(f"invalid publish-gate receipt row in {path}: {line}")
    if set(values) != {"revision", "tree"} or set(images) != set(IMAGES):
        raise RuntimeError(f"incomplete publish-gate receipt: {path}")
    for image, value in images.items():
        if not DIGEST.fullmatch(value):
            raise RuntimeError(f"publish-gate receipt is missing a valid ID for {image}")
    return GateReceipt(values["revision"], values["tree"], images)


def atomic_write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as pending:
        pending.write(contents)
        pending_path = Path(pending.name)
    pending_path.replace(path)


def write_receipt(path: Path, revision: str) -> None:
    if subprocess.run(["git", "check-ignore", "-q", str(path)], check=False).returncode != 0:
        raise RuntimeError(f"refusing to write a publish-gate receipt not ignored by git: {path}")
    tree = capture("git", "write-tree")
    images = {image: image_id(f"{image}:local") for image in IMAGES}
    contents = f"revision\t{revision}\ntree\t{tree}\n" + "".join(
        f"image\t{image}\t{images[image]}\n" for image in IMAGES
    )
    atomic_write(path, contents)


def verify_receipt(path: Path, revision: str) -> None:
    if not path.is_file():
        raise RuntimeError("no publish-gate receipt for this clone — run: just publish-gate")
    receipt = parse_receipt(path)
    if receipt.revision != revision:
        raise RuntimeError(f"publish-gate receipt names revision {receipt.revision}, expected {revision}")
    if receipt.tree != capture("git", "write-tree"):
        raise RuntimeError("publish-gate receipt covers different repository content")
    for image in IMAGES:
        current = image_id(f"{image}:local")
        if current != receipt.images[image]:
            raise RuntimeError(f"{image}:local changed after publish-gate: {current}, expected {receipt.images[image]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("write", "verify"))
    parser.add_argument("receipt", type=Path)
    parser.add_argument("revision")
    args = parser.parse_args()
    try:
        if args.command == "write":
            write_receipt(args.receipt, args.revision)
        else:
            verify_receipt(args.receipt, args.revision)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

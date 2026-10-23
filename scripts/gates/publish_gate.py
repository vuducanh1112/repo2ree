#!/usr/bin/env python3
"""Write and verify the publish gate's receipt: the revision, tree, and local image set it passed on."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from scripts.gates import receipts
from scripts.gates.receipts import PublishGateReceipt, ReceiptError

IMAGES = ("repo2ree-gui", "repo2ree-backend", "repo2ree-provider-docker")


def capture(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def image_id(image: str) -> str:
    return capture("docker", "image", "inspect", "--format", "{{.Id}}", image)


def write_receipt(path: Path, revision: str) -> None:
    images = {image: image_id(f"{image}:local") for image in IMAGES}
    try:
        receipt = PublishGateReceipt(
            revision=revision, tree=capture("git", "write-tree"), written=receipts.now(), images=images
        )
    except ValueError as error:
        raise ReceiptError(f"invalid local image ID among {images}") from error
    receipts.write(path, receipt)


def read_receipt(path: Path) -> PublishGateReceipt:
    receipt = receipts.read(PublishGateReceipt, path)
    if receipt is None:
        raise ReceiptError("no publish-gate receipt for this clone — run: just publish-gate")
    if set(receipt.images) != set(IMAGES):
        raise ReceiptError(f"the publish-gate receipt names {sorted(receipt.images)}, not {sorted(IMAGES)}")
    return receipt


def verify_receipt(path: Path, revision: str) -> None:
    receipt = read_receipt(path)
    if receipt.revision != revision:
        raise ReceiptError(f"publish-gate receipt names revision {receipt.revision}, expected {revision}")
    if receipt.tree != capture("git", "write-tree"):
        raise ReceiptError("publish-gate receipt covers different repository content")
    for image in IMAGES:
        current = image_id(f"{image}:local")
        if current != receipt.images[image]:
            raise ReceiptError(f"{image}:local changed after publish-gate: {current}, expected {receipt.images[image]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("write", "verify"))
    parser.add_argument("receipt", type=Path)
    parser.add_argument("revision")
    args = parser.parse_args()
    try:
        if args.command == "write":
            write_receipt(args.receipt, args.revision)
        else:
            verify_receipt(args.receipt, args.revision)
    except (ReceiptError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

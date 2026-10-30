#!/usr/bin/env python3
"""A platform's certified image set as archives: how a machine without registry credentials hands over its images.

Images are pushed from one host, the one holding registry credentials. Another
platform's images are built and gated on a machine of that platform, then travel
here as archives:

- ``export`` (``just archive-images``), on the machine that passed the publish gate:
  saves exactly the images its receipt certifies, by image ID, into
  ``<archive-dir>/<os>-<arch>/``, with a manifest binding the revision, tree,
  platform, image IDs, and each archive's digest;
- ``just machine fetch-archives <machine>`` brings the set to the pushing host;
- ``just publish-candidate`` there verifies the set, loads it, checks every loaded
  image is the certified one, and pushes it beside the host's own platform.

A set is only ever what a publish gate certified: nothing here builds an image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from scripts.gates import publish_gate

IMAGES = publish_gate.IMAGES
MANIFEST = "manifest.json"
REVISION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
PLATFORM = re.compile(r"[a-z0-9]+/[a-z0-9]+")
LOADED = re.compile(r"Loaded image ID: (sha256:[0-9a-f]{64})")


@dataclass(frozen=True)
class ArchiveSet:
    """A verified set: one platform's certified images, as archives in ``directory``."""

    directory: Path
    revision: str
    tree: str
    platform: str
    images: dict[str, str]  # Each image's certified ID.


def capture(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def platform_directory(root: Path, platform: str) -> Path:
    return root / platform.replace("/", "-")


def archive_name(image: str) -> str:
    return f"{image}.tar"


def seal(directory: Path, *, revision: str, tree: str, platform: str, images: dict[str, str]) -> None:
    """Write the manifest binding the archives in ``directory`` to what the publish gate certified."""
    if not REVISION.fullmatch(revision) or not PLATFORM.fullmatch(platform):
        raise RuntimeError(f"invalid image archive set: revision {revision!r}, platform {platform!r}")
    if set(images) != set(IMAGES) or not all(DIGEST.fullmatch(image_id) for image_id in images.values()):
        raise RuntimeError(f"an image archive set holds exactly {', '.join(IMAGES)}, each by its image ID")
    missing = [archive_name(image) for image in IMAGES if not (directory / archive_name(image)).is_file()]
    if missing:
        raise RuntimeError(f"image archive set is incomplete; missing: {' '.join(missing)}")
    document = {
        "schema": 2,
        "revision": revision,
        "tree": tree,
        "platform": platform,
        "images": images,
        "archives": {archive_name(image): file_digest(directory / archive_name(image)) for image in IMAGES},
    }
    (directory / MANIFEST).write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def verify(directory: Path) -> ArchiveSet:
    """The set in ``directory``, if its manifest is whole and every archive is the one it names."""
    path = directory / MANIFEST
    try:
        document = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise RuntimeError(f"no readable image archive manifest in {directory}: {error}") from None
    if not isinstance(document, dict) or document.get("schema") != 2:
        raise RuntimeError(f"not an image archive manifest: {path} (rebuild with 'just archive-images')")
    revision, tree, platform = document.get("revision"), document.get("tree"), document.get("platform")
    images, archives = document.get("images"), document.get("archives")
    if not (
        isinstance(revision, str)
        and REVISION.fullmatch(revision)
        and isinstance(tree, str)
        and isinstance(platform, str)
        and PLATFORM.fullmatch(platform)
        and isinstance(images, dict)
        and set(images) == set(IMAGES)
        and all(isinstance(value, str) and DIGEST.fullmatch(value) for value in images.values())
        and isinstance(archives, dict)
        and set(archives) == {archive_name(image) for image in IMAGES}
    ):
        raise RuntimeError(f"invalid image archive manifest: {path}")
    for name, expected in archives.items():
        archive = directory / name
        if not archive.is_file():
            raise RuntimeError(f"image archive set {directory} is missing {name}")
        if (actual := file_digest(archive)) != expected:
            raise RuntimeError(f"image archive {archive} changed: {actual}, expected {expected}")
    return ArchiveSet(directory, revision, tree, platform, dict(images))


def sets(root: Path) -> list[ArchiveSet]:
    """Every set under ``root``, verified; a set that does not verify is an error, not a skip."""
    return [verify(manifest.parent) for manifest in sorted(root.glob(f"*/{MANIFEST}"))]


def export(receipts: Path, root: Path) -> ArchiveSet:
    """Save the images this machine's current publish-gate receipt certifies as a set under ``root``."""
    receipt_path = publish_gate.receipt_path(receipts, publish_gate.platform())
    revision = capture("git", "describe", "--always")
    publish_gate.verify_receipt(receipt_path, revision)
    receipt = publish_gate.read_receipt(receipt_path)
    root.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix=".pending-", dir=root))
    try:
        for image in IMAGES:
            # By ID, never by tag: the certified image, not whatever `:local` names now.
            subprocess.run(
                ["docker", "save", "-o", str(pending / archive_name(image)), receipt.images[image]], check=True
            )
        seal(pending, revision=revision, tree=receipt.tree, platform=receipt.platform, images=receipt.images)
        target = platform_directory(root, receipt.platform)
        shutil.rmtree(target, ignore_errors=True)
        pending.rename(target)
    finally:
        shutil.rmtree(pending, ignore_errors=True)
    return verify(target)


def load(archive_set: ArchiveSet) -> None:
    """Load a verified set into the local daemon, refusing any image that is not the certified one."""
    for image in IMAGES:
        output = capture("docker", "load", "-i", str(archive_set.directory / archive_name(image)))
        loaded = LOADED.findall(output)
        if loaded != [archive_set.images[image]]:
            raise RuntimeError(
                f"{archive_name(image)} loaded {loaded or 'nothing'}, not the certified {archive_set.images[image]}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    export_parser = commands.add_parser("export")
    export_parser.add_argument("--receipts", type=Path, required=True)
    export_parser.add_argument("--archive-dir", type=Path, required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "export":
            archive_set = export(args.receipts, args.archive_dir)
            print(f">> archived the certified {archive_set.platform} images for {archive_set.revision}")
            print(f">> {archive_set.directory}; on the pushing host: just machine fetch-archives <this machine>")
        else:
            archive_set = verify(args.directory)
            print(f"{archive_set.platform} images for {archive_set.revision}: verified")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

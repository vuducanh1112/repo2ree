#!/usr/bin/env python3
"""Push, validate, and promote a protocol-compatible image set, for every published platform at once.

One host holds the registry credentials and pushes. Each platform's images are built and
gated on a machine of that platform: this host's own come from its daemon, by the image IDs
its publish-gate receipt certifies; the others arrive as archive sets
(``scripts/publish/image_archive_set.py``). ``push`` refuses unless every platform in
``--platforms`` is there, all for the same revision and tree.

- ``push``: each platform's images go up as ``<image>:<revision>-<os>-<arch>``, then
  ``<image>:<revision>`` becomes one index over them, in every registry. ``edge`` never moves here.
- ``validate``: on a machine of one platform, resolve the candidate's index digests (every
  registry must agree), run the showcase suite against exactly them, and record the
  platform's validation receipt under ``<state-dir>/<revision>/<os>-<arch>.json``.
- ``promote``: once every platform in the index has a validation receipt naming the same,
  still-current digests, ``edge`` becomes that index.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from scripts.gates import publish_gate
from scripts.publish import image_archive_set

IMAGES = ("repo2ree-provider-docker", "repo2ree-backend", "repo2ree-gui")
STACK_VARIABLES = {
    "repo2ree-provider-docker": "STACK_PROVIDER_IMAGE",
    "repo2ree-backend": "STACK_BACKEND_IMAGE",
    "repo2ree-gui": "STACK_GUI_IMAGE",
}
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
REVISION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
PLATFORM = re.compile(r"[a-z0-9]+/[a-z0-9]+")
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CandidateReceipt:
    """A candidate's index digest per (registry, image); ``platform`` is the one a validation ran on."""

    revision: str
    images: dict[tuple[str, str], str]
    platform: str = ""

    @property
    def registries(self) -> tuple[str, ...]:
        return tuple(sorted({registry for registry, _ in self.images}))


@dataclass(frozen=True)
class PlatformSet:
    """One platform's certified images, ready to push: local image IDs, from the daemon or loaded archives."""

    platform: str
    images: dict[str, str]


def capture(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def platform_tag(revision: str, platform: str) -> str:
    return f"{revision}-{platform.replace('/', '-')}"


def resolve_digest(reference: str) -> str:
    output = capture("docker", "buildx", "imagetools", "inspect", reference)
    values = [line.split(maxsplit=1)[1] for line in output.splitlines() if line.startswith("Digest:")]
    digest = values[0] if values else ""
    if not DIGEST.fullmatch(digest):
        raise RuntimeError(f"invalid manifest digest for {reference}: {digest}")
    return digest


def index_platforms(reference: str) -> set[str]:
    """The platforms an index names; attestation entries (``unknown/unknown``) are not platforms."""
    document = json.loads(capture("docker", "buildx", "imagetools", "inspect", "--raw", reference))
    found = {
        f"{entry['platform']['os']}/{entry['platform']['architecture']}"
        for entry in document.get("manifests", [])
        if entry.get("platform", {}).get("os") not in (None, "unknown")
    }
    if not found:
        raise RuntimeError(f"{reference} is not a multi-platform index")
    return found


def parse_receipt(path: Path) -> CandidateReceipt:
    try:
        document = json.loads(path.read_text())
        revision = document["revision"]
        platform = document.get("platform", "")
        rows = [(row["registry"], row["image"], row["digest"]) for row in document["images"]]
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f"invalid candidate receipt {path}: {error}") from None
    if not set(document) <= {"revision", "images", "platform"} or not isinstance(revision, str):
        raise RuntimeError(f"invalid candidate receipt {path}: expected a revision and images")
    if platform and not PLATFORM.fullmatch(platform):
        raise RuntimeError(f"invalid candidate receipt {path}: platform {platform!r}")
    images: dict[tuple[str, str], str] = {}
    for registry, image, digest in rows:
        if image not in IMAGES:
            raise RuntimeError(f"invalid candidate receipt row in {path}: {registry}/{image}")
        if (registry, image) in images:
            raise RuntimeError(f"duplicate image row in {path}: {registry}/{image}")
        if not DIGEST.fullmatch(digest):
            raise RuntimeError(f"invalid digest in {path}: {digest}")
        images[(registry, image)] = digest
    if not images:
        raise RuntimeError(f"incomplete validation receipt: {path}")
    receipt = CandidateReceipt(revision, images, platform)
    for registry in receipt.registries:
        missing = [image for image in IMAGES if (registry, image) not in images]
        if missing:
            raise RuntimeError(f"validation receipt is missing {registry}/{missing[0]}")
    return receipt


def serialize_receipt(receipt: CandidateReceipt) -> str:
    rows = [
        {"registry": registry, "image": image, "digest": digest}
        for (registry, image), digest in sorted(receipt.images.items())
    ]
    document: dict[str, object] = {"revision": receipt.revision, "images": rows}
    if receipt.platform:
        document["platform"] = receipt.platform
    return json.dumps(document, indent=2) + "\n"


def assert_revision(revision: str) -> None:
    if not REVISION.fullmatch(revision):
        raise RuntimeError(f"invalid image candidate revision: {revision}")


def assert_ignored(path: Path) -> None:
    if subprocess.run(["git", "check-ignore", "-q", str(path)], check=False).returncode != 0:
        raise RuntimeError(f"refusing to write a validation receipt not ignored by git: {path}")


def resolve_candidate(revision: str, registries: list[str]) -> CandidateReceipt:
    assert_revision(revision)
    if not registries:
        raise RuntimeError("at least one registry namespace is required")
    records: dict[tuple[str, str], str] = {}
    for image in IMAGES:
        expected: str | None = None
        for registry in registries:
            digest = resolve_digest(f"{registry}/{image}:{revision}")
            if expected is not None and digest != expected:
                raise RuntimeError(f"registries disagree for {image}: {expected} != {digest}")
            expected = digest
            records[(registry, image)] = digest
    return CandidateReceipt(revision, records)


def write_receipt(path: Path, receipt: CandidateReceipt) -> None:
    assert_ignored(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as pending:
        pending.write(serialize_receipt(receipt))
        pending_path = Path(pending.name)
    pending_path.replace(path)


def validation_path(state_dir: Path, revision: str, platform: str) -> Path:
    return state_dir / revision / f"{platform.replace('/', '-')}.json"


def verify_candidate(revision: str, state_dir: Path) -> CandidateReceipt:
    """The candidate's digests, if every platform in its index was validated against them and they still hold."""
    paths = sorted((state_dir / revision).glob("*.json"))
    if not paths:
        raise RuntimeError(f"no validation receipt for image candidate {revision} under {state_dir / revision}")
    validated = [parse_receipt(path) for path in paths]
    first = validated[0]
    for receipt in validated:
        if receipt.revision != revision:
            raise RuntimeError(f"a validation receipt under {state_dir / revision} names {receipt.revision}")
        if receipt.images != first.images:
            raise RuntimeError(f"the {receipt.platform} and {first.platform} validations saw different digests")
    for registry in first.registries:
        for image in IMAGES:
            expected = first.images[(registry, image)]
            current = resolve_digest(f"{registry}/{image}:{revision}")
            if current != expected:
                raise RuntimeError(f"{registry}/{image}:{revision} changed: {current}, expected {expected}")
    registry = first.registries[0]
    for image in IMAGES:
        unvalidated = index_platforms(f"{registry}/{image}@{first.images[(registry, image)]}") - {
            receipt.platform for receipt in validated
        }
        if unvalidated:
            raise RuntimeError(f"{image}:{revision} is not validated on {', '.join(sorted(unvalidated))}")
    return first


def image_environment(receipt: CandidateReceipt, registry: str) -> dict[str, str]:
    environment: dict[str, str] = {}
    for image in IMAGES:
        try:
            digest = receipt.images[(registry, image)]
        except KeyError as error:
            raise RuntimeError(f"{registry}/{image} is not in the validation receipt") from error
        environment[STACK_VARIABLES[image]] = f"{registry}/{image}@{digest}"
    return environment


def promote_candidate(revision: str, state_dir: Path) -> None:
    receipt = verify_candidate(revision, state_dir)
    for registry in receipt.registries:
        for image in IMAGES:
            digest = receipt.images[(registry, image)]
            target = f"{registry}/{image}:edge"
            print(f">> {target}: {digest}")
            # The index itself, every platform in it: edge names the same digest the candidate does.
            run("docker", "buildx", "imagetools", "create", "-t", target, f"{registry}/{image}@{digest}")
            if resolve_digest(target) != digest:
                raise RuntimeError(f"promotion verification failed for {target}")


def platform_sets(
    revision: str, receipts: Path, archives: Path, required: list[str], *, load: bool = True
) -> list[PlatformSet]:
    """This host's certified images and every archived platform's, all for ``revision`` and this tree."""
    local_platform = publish_gate.platform()
    receipt_path = publish_gate.receipt_path(receipts, local_platform)
    publish_gate.verify_receipt(receipt_path, revision)
    local = publish_gate.read_receipt(receipt_path)
    found = [PlatformSet(local_platform, dict(local.images))]
    for archived in image_archive_set.sets(archives) if archives.is_dir() else []:
        if archived.platform == local_platform:
            continue  # This host's own platform goes up from its daemon, as its receipt certifies.
        if archived.revision != revision or archived.tree != local.tree:
            raise RuntimeError(
                f"the {archived.platform} archives are for {archived.revision} (tree {archived.tree[:12]}),"
                f" not {revision} (tree {local.tree[:12]}): archive them again on their machine"
            )
        if load:
            image_archive_set.load(archived)
        found.append(PlatformSet(archived.platform, archived.images))
    missing = sorted(set(required) - {platform_set.platform for platform_set in found})
    if missing:
        raise RuntimeError(
            f"no certified images for {', '.join(missing)}: run the publish gate and just archive-images on a"
            " machine of that platform, then just machine fetch-archives <machine> here"
        )
    return found


def push_candidate(
    revision: str,
    registries: list[str],
    receipts: Path,
    archives: Path,
    platforms: list[str],
    *,
    require_current: bool = False,
) -> None:
    assert_revision(revision)
    if revision == "edge":
        raise RuntimeError(
            "image-set pushes require a non-edge candidate tag; edge moves only through validated promotion"
        )
    if not registries:
        raise RuntimeError("at least one registry namespace is required")
    if require_current:
        current = capture("git", "describe", "--always", "--dirty")
        if revision != current:
            raise RuntimeError(f"image candidate must name the clean tree being built ({current})")
    sets = platform_sets(revision, receipts, archives, platforms)
    for registry in registries:
        for image in IMAGES:
            sources = []
            for platform_set in sets:
                # By certified ID, never by a mutable local tag.
                target = f"{registry}/{image}:{platform_tag(revision, platform_set.platform)}"
                run("docker", "tag", platform_set.images[image], target)
                run("docker", "push", target)
                sources.append(f"{registry}/{image}@{resolve_digest(target)}")
            run("docker", "buildx", "imagetools", "create", "-t", f"{registry}/{image}:{revision}", *sources)


def validate_candidate(revision: str, state_dir: Path, validation_registry: str, registry_names: list[str]) -> None:
    platform = publish_gate.platform()
    receipt_path = validation_path(state_dir, revision, platform)
    pending = Path(f"{receipt_path}.pending")
    pending.unlink(missing_ok=True)
    try:
        resolved = resolve_candidate(revision, registry_names)
        write_receipt(pending, CandidateReceipt(revision, resolved.images, platform))
        # The index digests: this machine's daemon pulls its own platform's images from them.
        environment = {**os.environ, **image_environment(parse_receipt(pending), validation_registry)}
        subprocess.run(
            [
                sys.executable,
                "-m",
                "repo2ree_testbed",
                "image-suite",
                "--suite",
                "showcase",
                "--compute-locations",
                "2",
                "--images",
                "published",
                "--repository",
                validation_registry,
                "--tag",
                revision,
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        pending.replace(receipt_path)
    finally:
        pending.unlink(missing_ok=True)
    print(f">> image candidate {revision} validated on {platform} — receipt written")


def chosen_revision(explicit: str, configured: str, *, allow_dirty: bool) -> str:
    revision = explicit or configured or capture("git", "describe", "--always", "--dirty")
    if not allow_dirty and revision.endswith("-dirty"):
        raise RuntimeError("tree is dirty — name the image candidate explicitly")
    assert_revision(revision)
    return revision


def registries(value: str) -> list[str]:
    return shlex.split(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("resolve", "verify", "promote", "environment", "push", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--revision", default="")
        command.add_argument("--configured-revision", default="")
        if name in {"resolve", "environment"}:
            command.add_argument("--receipt", type=Path, required=True)
        if name in {"verify", "promote", "validate"}:
            command.add_argument("--state-dir", type=Path, required=True)
        if name in {"resolve", "push", "validate"}:
            command.add_argument("--registries", required=True)
        if name == "environment":
            command.add_argument("--registry", required=True)
        if name == "push":
            command.add_argument("--receipts", type=Path, required=True, help="where the publish-gate receipts are")
            command.add_argument("--archives", type=Path, required=True, help="where archived platform sets are")
            command.add_argument("--platforms", required=True, help="every platform the candidate must carry")
            command.add_argument("--require-current", action="store_true")
        if name == "validate":
            command.add_argument("--validation-registry", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        revision = chosen_revision(args.revision, args.configured_revision, allow_dirty=args.command == "push")
        if args.command == "resolve":
            write_receipt(args.receipt, resolve_candidate(revision, registries(args.registries)))
        elif args.command == "verify":
            verify_candidate(revision, args.state_dir)
        elif args.command == "promote":
            promote_candidate(revision, args.state_dir)
            print(f">> promoted validated image candidate {revision} to edge")
        elif args.command == "environment":
            for name, value in image_environment(parse_receipt(args.receipt), args.registry).items():
                print(f"{name}={shlex.quote(value)}")
        elif args.command == "push":
            push_candidate(
                revision,
                registries(args.registries),
                args.receipts,
                args.archives,
                shlex.split(args.platforms),
                require_current=args.require_current,
            )
            print(f">> pushed image candidate :{revision} for {args.platforms}")
            print(f">> next, on a machine of each platform: just validate-candidate {revision}")
        elif args.command == "validate":
            validate_candidate(revision, args.state_dir, args.validation_registry, registries(args.registries))
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

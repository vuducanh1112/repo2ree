#!/usr/bin/env python3
"""Resolve, validate, push, and promote protocol-compatible image sets."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

IMAGES = ("repo2ree-provider-docker", "repo2ree-backend", "repo2ree-gui")
STACK_VARIABLES = {
    "repo2ree-provider-docker": "STACK_PROVIDER_IMAGE",
    "repo2ree-backend": "STACK_BACKEND_IMAGE",
    "repo2ree-gui": "STACK_GUI_IMAGE",
}
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
REVISION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CandidateReceipt:
    revision: str
    images: dict[tuple[str, str], str]

    @property
    def registries(self) -> tuple[str, ...]:
        return tuple(sorted({registry for registry, _ in self.images}))


def capture(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def resolve_digest(reference: str) -> str:
    output = capture("docker", "buildx", "imagetools", "inspect", reference)
    values = [line.split(maxsplit=1)[1] for line in output.splitlines() if line.startswith("Digest:")]
    digest = values[0] if values else ""
    if not DIGEST.fullmatch(digest):
        raise RuntimeError(f"invalid manifest digest for {reference}: {digest}")
    return digest


def parse_receipt(path: Path) -> CandidateReceipt:
    revision: str | None = None
    images: dict[tuple[str, str], str] = {}
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) == 2 and fields[0] == "revision" and revision is None:
            revision = fields[1]
        elif len(fields) == 4 and fields[0] == "image" and fields[2] in IMAGES:
            key = (fields[1], fields[2])
            if key in images:
                raise RuntimeError(f"duplicate image row in {path}: {fields[1]}/{fields[2]}")
            if not DIGEST.fullmatch(fields[3]):
                raise RuntimeError(f"invalid digest in {path}: {fields[3]}")
            images[key] = fields[3]
        else:
            raise RuntimeError(f"invalid candidate receipt row in {path}: {line}")
    if revision is None or not images:
        raise RuntimeError(f"incomplete validation receipt: {path}")
    receipt = CandidateReceipt(revision, images)
    for registry in receipt.registries:
        missing = [image for image in IMAGES if (registry, image) not in images]
        if missing:
            raise RuntimeError(f"validation receipt is missing {registry}/{missing[0]}")
    return receipt


def serialize_receipt(receipt: CandidateReceipt) -> str:
    rows = [f"image\t{registry}\t{image}\t{digest}" for (registry, image), digest in receipt.images.items()]
    return f"revision\t{receipt.revision}\n" + "\n".join(sorted(rows)) + "\n"


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


def verify_candidate(revision: str, path: Path) -> CandidateReceipt:
    if not path.is_file():
        raise RuntimeError(f"no validation receipt for image candidate {revision}: {path}")
    receipt = parse_receipt(path)
    if receipt.revision != revision:
        raise RuntimeError(f"validation receipt does not name image candidate {revision}")
    for registry in receipt.registries:
        for image in IMAGES:
            expected = receipt.images[(registry, image)]
            current = resolve_digest(f"{registry}/{image}:{revision}")
            if current != expected:
                raise RuntimeError(f"{registry}/{image}:{revision} changed: {current}, expected {expected}")
    return receipt


def image_environment(receipt: CandidateReceipt, registry: str) -> dict[str, str]:
    environment: dict[str, str] = {}
    for image in IMAGES:
        try:
            digest = receipt.images[(registry, image)]
        except KeyError as error:
            raise RuntimeError(f"{registry}/{image} is not in the validation receipt") from error
        environment[STACK_VARIABLES[image]] = f"{registry}/{image}@{digest}"
    return environment


def promote_candidate(revision: str, path: Path) -> None:
    receipt = verify_candidate(revision, path)
    for registry in receipt.registries:
        for image in IMAGES:
            digest = receipt.images[(registry, image)]
            target = f"{registry}/{image}:edge"
            print(f">> {target}: {digest}")
            subprocess.run(
                [
                    "docker",
                    "buildx",
                    "imagetools",
                    "create",
                    "--prefer-index=false",
                    "-t",
                    target,
                    f"{registry}/{image}@{digest}",
                ],
                check=True,
            )
            if resolve_digest(target) != digest:
                raise RuntimeError(f"promotion verification failed for {target}")


def gate_images(path: Path) -> dict[str, str]:
    images: dict[str, str] = {}
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) == 3 and fields[0] == "image" and fields[1] in IMAGES:
            images[fields[1]] = fields[2]
    for image in IMAGES:
        if not DIGEST.fullmatch(images.get(image, "")):
            raise RuntimeError(f"publish-gate receipt is missing a valid ID for {image}")
    return images


def verify_publish_gate(path: Path, revision: str) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/publish/publish_gate_receipt.py"), "verify", str(path), revision],
        cwd=ROOT,
        check=True,
    )


def push_candidate(
    revision: str,
    registries: list[str],
    gate_receipt: Path | None,
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
    if gate_receipt:
        verify_publish_gate(gate_receipt, revision)
    certified = gate_images(gate_receipt) if gate_receipt else {}
    for registry in registries:
        for image in IMAGES:
            source = certified.get(image, f"{image}:local")
            target = f"{registry}/{image}:{revision}"
            subprocess.run(["docker", "tag", source, target], check=True)
            subprocess.run(["docker", "push", target], check=True)


def push_archive(archive_dir: Path, registry_names: list[str]) -> str:
    stamp = archive_dir / "IMAGE_CANDIDATE_REV"
    if not stamp.is_file() or not (revision := stamp.read_text().strip()):
        raise RuntimeError(f"no IMAGE_CANDIDATE_REV stamp in {archive_dir} — build with 'just archive-images'")
    push_candidate(revision, registry_names, None)
    return revision


def validate_candidate(revision: str, state_dir: Path, validation_registry: str, registry_names: list[str]) -> None:
    receipt = state_dir / f"{revision}.validated"
    pending = Path(f"{receipt}.pending")
    pending.unlink(missing_ok=True)
    try:
        write_receipt(pending, resolve_candidate(revision, registry_names))
        environment = {**os.environ, **image_environment(parse_receipt(pending), validation_registry)}
        suite = ROOT / "scripts/test-stack/run_image_suite.py"
        for name, locations in (("e2e-gui", "2"), ("e2e-gui-review", "1")):
            subprocess.run(
                [
                    sys.executable,
                    str(suite),
                    "--suite",
                    name,
                    "--compute-locations",
                    locations,
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
        pending.replace(receipt)
    finally:
        pending.unlink(missing_ok=True)
    print(f">> image candidate {revision} validated — receipt written")


def chosen_revision(explicit: str, configured: str, *, allow_dirty: bool) -> str:
    revision = explicit or configured or capture("git", "describe", "--always", "--dirty")
    if not allow_dirty and revision.endswith("-dirty"):
        raise RuntimeError("tree is dirty — name the image candidate explicitly")
    assert_revision(revision)
    return revision


def registries(value: str) -> list[str]:
    return shlex.split(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("resolve", "verify", "promote", "environment", "push", "validate", "push-archive"):
        command = commands.add_parser(name)
        if name != "push-archive":
            command.add_argument("--revision", default="")
            command.add_argument("--configured-revision", default="")
        if name in {"resolve", "environment"}:
            command.add_argument("--receipt", type=Path, required=True)
        if name in {"verify", "promote"}:
            receipt = command.add_mutually_exclusive_group(required=True)
            receipt.add_argument("--receipt", type=Path)
            receipt.add_argument("--state-dir", type=Path)
        if name in {"resolve", "push", "validate", "push-archive"}:
            command.add_argument("--registries", required=True)
        if name == "environment":
            command.add_argument("--registry", required=True)
        if name == "push":
            command.add_argument("--gate-receipt", type=Path)
            command.add_argument("--require-current", action="store_true")
        if name == "validate":
            command.add_argument("--state-dir", type=Path, required=True)
            command.add_argument("--validation-registry", required=True)
        if name == "push-archive":
            command.add_argument("--archive-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "push-archive":
            revision = push_archive(args.archive_dir, registries(args.registries))
            print(f">> pushed image candidate :{revision}")
            print(f">> next: just validate-candidate {revision}")
            return 0
        revision = chosen_revision(args.revision, args.configured_revision, allow_dirty=args.command == "push")
        receipt = (
            args.state_dir / f"{revision}.validated"
            if args.command in {"verify", "promote"} and args.state_dir
            else getattr(args, "receipt", None)
        )
        if args.command == "resolve":
            write_receipt(args.receipt, resolve_candidate(revision, registries(args.registries)))
        elif args.command == "verify":
            if receipt is None:
                raise RuntimeError("candidate receipt path is required")
            verify_candidate(revision, receipt)
        elif args.command == "promote":
            if receipt is None:
                raise RuntimeError("candidate receipt path is required")
            promote_candidate(revision, receipt)
            print(f">> promoted validated image candidate {revision} to edge")
        elif args.command == "environment":
            for name, value in image_environment(parse_receipt(args.receipt), args.registry).items():
                print(f"{name}={shlex.quote(value)}")
        elif args.command == "push":
            push_candidate(
                revision,
                registries(args.registries),
                args.gate_receipt,
                require_current=args.require_current,
            )
            print(f">> pushed image candidate :{revision}")
            print(f">> next: just validate-candidate {revision} && just promote-candidate {revision}")
        elif args.command == "validate":
            validate_candidate(
                revision,
                args.state_dir,
                args.validation_registry,
                registries(args.registries),
            )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Receipts: what a gate proved, bound to the content it proved it on.

Every gate writes one JSON receipt under ``.receipts/``: the same header (which gate, the
revision and tree it covered, when it was written) and a body of its own. A receipt
describes one clone's validation state and is never committed: a tracked receipt would be
part of the tree it measures, so no receipt could ever match twice. ``write`` refuses a
receipt git does not ignore.

Standard library only: the pre-commit hook reads the commit gate's receipt on whatever
Python pre-commit runs, not the workspace's.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal, Self

DIRECTORY = ".receipts"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
PLATFORM = re.compile(r"[a-z0-9]+/[a-z0-9]+")

type Gate = Literal["commit-gate", "assurance-gate", "publish-gate", "tier"]
type Document = dict[str, Any]


class ReceiptError(RuntimeError):
    """A receipt is missing, unreadable, or covers something other than what is asked."""


@dataclass(frozen=True)
class Receipt:
    GATE: ClassVar[Gate]

    # The commit it covered; None for the commit gate, which runs before its commit exists.
    revision: str | None
    tree: str
    written: datetime

    @classmethod
    def from_document(cls, document: Document) -> Self:
        expected = {"gate", *(field.name for field in fields(cls))}
        if set(document) != expected:
            raise ValueError(f"fields {sorted(document)}, expected {sorted(expected)}")
        if document["gate"] != cls.GATE:
            raise ValueError(f"written by {document['gate']!r}")
        header: Document = {
            "revision": _optional_str(document, "revision"),
            "tree": _str(document, "tree"),
            "written": datetime.fromisoformat(_str(document, "written")),
        }
        return cls(**header, **cls.body(document))

    @classmethod
    def body(cls, document: Document) -> Document:
        """This gate's own fields, read from the document."""
        return {}

    def to_document(self) -> Document:
        return {"gate": self.GATE, **asdict(self), "written": self.written.isoformat()}


@dataclass(frozen=True)
class CommitGateReceipt(Receipt):
    """Checks, the docs build, and unit tests passed on exactly this staged tree."""

    GATE: ClassVar[Gate] = "commit-gate"


@dataclass(frozen=True)
class TestVerdict:
    __test__: ClassVar[bool] = False  # Not a pytest class, despite the name.

    run: str
    test: str
    outcome: str
    behaviour: str
    excused: str | None = None  # The expected-verdicts.toml reason that accepted it.

    @classmethod
    def from_document(cls, document: Any) -> TestVerdict:
        if not isinstance(document, dict) or not set(document) <= {field.name for field in fields(cls)}:
            raise ValueError(f"not a test verdict: {document}")
        return cls(
            run=_str(document, "run"),
            test=_str(document, "test"),
            outcome=_str(document, "outcome"),
            behaviour=_str(document, "behaviour"),
            excused=_optional_str(document, "excused"),
        )


@dataclass(frozen=True)
class Coverage:
    declared: int
    reached: int
    unreached: tuple[str, ...]


@dataclass(frozen=True)
class AssuranceGateReceipt(Receipt):
    """Every gated e2e test on HEAD, judged by the checker, together reaching the specification."""

    GATE: ClassVar[Gate] = "assurance-gate"

    runs: tuple[str, ...]
    tests: tuple[TestVerdict, ...]
    coverage: Coverage

    @classmethod
    def body(cls, document: Document) -> Document:
        coverage = _object(document, "coverage")
        if set(coverage) != {field.name for field in fields(Coverage)}:
            raise ValueError(f"coverage fields {sorted(coverage)}")
        return {
            "runs": tuple(_strs(document, "runs")),
            "tests": tuple(TestVerdict.from_document(test) for test in _list(document, "tests")),
            "coverage": Coverage(
                declared=_int(coverage, "declared"),
                reached=_int(coverage, "reached"),
                unreached=tuple(_strs(coverage, "unreached")),
            ),
        }


@dataclass(frozen=True)
class PublishGateReceipt(Receipt):
    """The publish gate passed on this revision with these local images, built for this platform.

    One per platform: each published platform's image set is built and gated on a machine of
    its own (``.receipts/publish-gate-<os>-<arch>.json``), so one never overwrites another when
    a machine's receipts are brought back.
    """

    GATE: ClassVar[Gate] = "publish-gate"

    images: dict[str, str]  # Each image's local ID.
    platform: str  # The os/arch of the daemon holding them, as an image platform names it.

    def __post_init__(self) -> None:
        for image, digest in self.images.items():
            if not DIGEST.fullmatch(digest):
                raise ValueError(f"invalid local image ID for {image}: {digest}")
        if not PLATFORM.fullmatch(self.platform):
            raise ValueError(f"invalid platform: {self.platform!r}")

    @classmethod
    def body(cls, document: Document) -> Document:
        images = _object(document, "images")
        return {"images": {image: _str(images, image) for image in images}, "platform": _str(document, "platform")}


@dataclass(frozen=True)
class TierReceipt(Receipt):
    """One gated tier passed, whole, on this tree and platform, with the deployment the policy asks.

    Written by ``scripts/gates/tiers.py`` from the run's own record, never by the tier itself,
    at ``.receipts/tiers/<tier>/<tree>-<os>-<arch>.json``: a receipt per tree and platform, so
    one for another branch's tree counts again when that tree is checked out again.
    """

    GATE: ClassVar[Gate] = "tier"

    tier: str
    platform: str
    machine: str
    run: str  # The run directory its record is in.
    tests: int
    skipped: int
    judged: bool  # Whether every test's behaviour was checked too, and passed or was excused.

    def __post_init__(self) -> None:
        if not PLATFORM.fullmatch(self.platform):
            raise ValueError(f"invalid platform: {self.platform!r}")

    @classmethod
    def body(cls, document: Document) -> Document:
        judged = document.get("judged")
        if not isinstance(judged, bool):
            raise ValueError("judged is not a boolean")
        return {
            "tier": _str(document, "tier"),
            "platform": _str(document, "platform"),
            "machine": _str(document, "machine"),
            "run": _str(document, "run"),
            "tests": _int(document, "tests"),
            "skipped": _int(document, "skipped"),
            "judged": judged,
        }


def tier_path(root: Path, tier: str, tree: str, platform: str) -> Path:
    return root / DIRECTORY / "tiers" / tier / f"{tree}-{platform.replace('/', '-')}.json"


def path(root: Path, gate: Gate) -> Path:
    return root / DIRECTORY / f"{gate}.json"


def now() -> datetime:
    return datetime.now(UTC)


def write(path: Path, receipt: Receipt) -> None:
    """Replace the receipt at ``path`` atomically, refusing one git would track."""
    if subprocess.run(["git", "check-ignore", "-q", str(path)], check=False).returncode != 0:
        raise ReceiptError(
            f"refusing to write {path}: git does not ignore it, and a tracked receipt changes the tree it "
            f"covers. Restore {DIRECTORY}/.gitignore."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as pending:
        pending.write(json.dumps(receipt.to_document(), indent=2) + "\n")
    Path(pending.name).replace(path)


def read[R: Receipt](model: type[R], path: Path) -> R | None:
    """The receipt at ``path``, or None when there is none; a ReceiptError when the file is not one."""
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None
    try:
        document = json.loads(text)
        if not isinstance(document, dict):
            raise ValueError("not a JSON object")
        return model.from_document(document)
    except ValueError as error:
        raise ReceiptError(f"{path}: not a {model.GATE} receipt ({error}); run the gate again") from None


# Each reads one field and refuses a wrong type, so a receipt is never half-read.


def _str(document: Document, name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str):
        raise ValueError(f"{name} is not a string")
    return value


def _optional_str(document: Document, name: str) -> str | None:
    return None if document.get(name) is None else _str(document, name)


def _int(document: Document, name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} is not an integer")
    return value


def _list(document: Document, name: str) -> list[Any]:
    value = document.get(name)
    if not isinstance(value, list):
        raise ValueError(f"{name} is not a list")
    return value


def _strs(document: Document, name: str) -> list[str]:
    values = _list(document, name)
    if not all(isinstance(value, str) for value in values):
        raise ValueError(f"{name} holds something other than strings")
    return values


def _object(document: Document, name: str) -> Document:
    value = document.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"{name} is not an object")
    return value

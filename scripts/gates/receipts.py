"""Receipts: what a gate proved, bound to the content it proved it on.

Every gate writes one JSON receipt under ``.receipts/``: the same header (which gate, the
revision and tree it covered, when it was written) and a body of its own. A receipt
describes one clone's validation state and is never committed: a tracked receipt would be
part of the tree it measures, so no receipt could ever match twice. ``write`` refuses a
receipt git does not ignore.
"""

from __future__ import annotations

import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

DIRECTORY = ".receipts"

type Gate = Literal["commit-gate", "assurance-gate", "publish-gate"]
type Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


class ReceiptError(RuntimeError):
    """A receipt is missing, unreadable, or covers something other than what is asked."""


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Receipt(Model):
    gate: Gate
    # The commit it covered; None for the commit gate, which runs before its commit exists.
    revision: str | None
    tree: str
    written: datetime


class CommitGateReceipt(Receipt):
    """Checks, the docs build, and unit tests passed on exactly this staged tree."""

    gate: Literal["commit-gate"] = "commit-gate"


class TestVerdict(Model):
    run: str
    test: str
    outcome: str
    behaviour: str
    excused: str | None = None  # The expected-verdicts.toml reason that accepted it.


class Coverage(Model):
    declared: int
    reached: int
    unreached: tuple[str, ...]


class AssuranceGateReceipt(Receipt):
    """Every gated e2e test on HEAD, judged by the checker, together reaching the specification."""

    gate: Literal["assurance-gate"] = "assurance-gate"
    runs: tuple[str, ...]
    tests: tuple[TestVerdict, ...]
    coverage: Coverage


class PublishGateReceipt(Receipt):
    """The publish gate passed on this revision with these local images."""

    gate: Literal["publish-gate"] = "publish-gate"
    images: dict[str, Digest]  # Each image's local ID.


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
        pending.write(receipt.model_dump_json(indent=2) + "\n")
    Path(pending.name).replace(path)


def read[R: Receipt](model: type[R], path: Path) -> R | None:
    """The receipt at ``path``, or None when there is none; a ReceiptError when the file is not one."""
    try:
        return model.model_validate_json(path.read_text())
    except FileNotFoundError:
        return None
    except ValidationError as exc:
        raise ReceiptError(
            f"{path}: not a receipt this gate wrote ({exc.error_count()} problems); run it again"
        ) from None

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

PROCESS: Final = "environment"
OWNER: Final = "environment"

type Part = Literal["overlay", "records", "history"]


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Opened(_Record):
    kind: Literal["journal.opened"] = "journal.opened"
    process: str = PROCESS
    epoch: int = 1
    hosts: tuple[str, ...] = (PROCESS,)


class _Closed(_Record):
    kind: Literal["journal.closed"] = "journal.closed"
    final: bool = True


class _Drifted(_Record):
    kind: Literal["transition"] = "transition"
    owner: str = OWNER
    subject: Literal["Drift"] = "Drift"
    key: str
    partition: str
    to: Literal["arisen"] = "arisen"
    facts: dict[str, str]


class _Undone(_Record):
    kind: Literal["transition"] = "transition"
    owner: str = OWNER
    subject: Literal["Drift"] = "Drift"
    key: str
    partition: str
    from_: Literal["arisen"] = Field(default="arisen", alias="from")
    to: Literal["undone"] = "undone"
    facts: dict[str, str] = Field(default_factory=dict)


class _Message(_Record):
    kind: Literal["send", "receive"]
    owner: str = OWNER
    subject: Literal["run_command"] = "run_command"
    message: Literal["run_command", "exited"]
    key: str
    partition: str
    facts: dict[str, str | int]


class _BundleMessage(_Record):
    kind: Literal["send", "receive"]
    owner: str = OWNER
    subject: Literal["export_bundle"] = "export_bundle"
    message: Literal["export_bundle", "exported", "refused"]
    key: str
    partition: str
    facts: dict[str, int | list[str]]


def part_of(path: str) -> Part:
    parts = PurePosixPath(path).parts
    top = parts[2] if parts[0] == "reviews" and len(parts) > 2 else parts[0]
    if top == ".git":
        return "history"
    return "overlay" if top == "overlay" else "records"


class EnvironmentJournal:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.id = f"{PROCESS}-000001"
        self.path = directory / f"{self.id}.ndjson"
        self._sequence = 0
        self.path.write_text("", encoding="utf-8")
        self._append(_Opened())

    def _append(self, record: _Record) -> str:
        self._sequence += 1
        dumped = record.model_dump(mode="json", by_alias=True)
        fields = {"v": 1, "seq": self._sequence, **dumped, "at": datetime.now(UTC).isoformat()}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(fields, separators=(",", ":"), sort_keys=True) + "\n")
        return f"{self.id}#{self._sequence}"

    def drifted(self, key: str, ree: str, path: str) -> None:
        self._append(_Drifted(key=key, partition=ree, facts={"path": path, "part": part_of(path)}))

    def undone(self, key: str, ree: str) -> None:
        self._append(_Undone(key=key, partition=ree))

    def command(self, attempt_id: str, ree: str, run_id: str) -> str:
        facts: dict[str, str | int] = {"run_id": run_id}
        return self._append(_Message(kind="send", message="run_command", key=attempt_id, partition=ree, facts=facts))

    def exited(self, attempt_id: str, ree: str, exit: int, commit: str | None, record: str | None) -> None:  # noqa: A002
        facts: dict[str, str | int] = {"exit": exit}
        facts |= {"commit": commit} if commit else {}
        facts |= {"record": record} if record else {}
        self._append(_Message(kind="receive", message="exited", key=attempt_id, partition=ree, facts=facts))

    def bundle(self, bundle_id: str, ree: str) -> None:
        self._append(_BundleMessage(kind="send", message="export_bundle", key=bundle_id, partition=ree, facts={}))

    def exported(self, bundle_id: str, ree: str, heads: list[str] | None) -> None:
        facts: dict[str, int | list[str]] = {"heads": heads} if heads is not None else {}
        self._append(_BundleMessage(kind="receive", message="exported", key=bundle_id, partition=ree, facts=facts))

    def refused(self, bundle_id: str, ree: str, exit: int) -> None:  # noqa: A002
        facts: dict[str, int | list[str]] = {"exit": exit}
        self._append(_BundleMessage(kind="receive", message="refused", key=bundle_id, partition=ree, facts=facts))

    def close(self) -> None:
        self._append(_Closed())

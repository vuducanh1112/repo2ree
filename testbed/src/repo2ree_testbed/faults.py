"""Faults a test asks its stack to inject, by real means, at the step it chooses.

A workbench fault names the REE whose workbench it hits: the workbench serving its store.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from repo2ree_testbed.records import Record

FAULTS_URL = "E2E_FAULTS_URL"


class KillWorkbench(Record):
    kind: Literal["kill_workbench"] = "kill_workbench"
    ree_id: str


class PauseWorkbench(Record):
    kind: Literal["pause_workbench"] = "pause_workbench"
    ree_id: str


class ResumeWorkbench(Record):
    kind: Literal["resume_workbench"] = "resume_workbench"
    ree_id: str


class PartitionWorkbench(Record):
    kind: Literal["partition_workbench"] = "partition_workbench"
    ree_id: str


class HealWorkbench(Record):
    kind: Literal["heal_workbench"] = "heal_workbench"
    ree_id: str


class LockHistory(Record):
    """A stale lock on the REE's history ref, as a crashed git process leaves one: no attempt can publish."""

    kind: Literal["lock_history"] = "lock_history"
    ree_id: str


class UnlockHistory(Record):
    kind: Literal["unlock_history"] = "unlock_history"
    ree_id: str


class CrashApi(Record):
    kind: Literal["crash_api"] = "crash_api"


type Fault = Annotated[
    KillWorkbench
    | PauseWorkbench
    | ResumeWorkbench
    | PartitionWorkbench
    | HealWorkbench
    | LockHistory
    | UnlockHistory
    | CrashApi,
    Field(discriminator="kind"),
]
FAULT = TypeAdapter[Fault](Fault)


class FaultRefusedError(RuntimeError):
    pass


def inject(url: str, fault: Fault) -> None:
    body = FAULT.dump_json(fault)
    headers = {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)  # noqa: S310 - the stack this test runs on
    try:
        with urllib.request.urlopen(request, timeout=180):  # noqa: S310 - the stack this test runs on
            return
    except urllib.error.HTTPError as error:
        raise FaultRefusedError(f"{fault.kind}: {error.read().decode(errors='replace')}") from error

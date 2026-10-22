"""Faults a test asks its stack to inject, by real means, at the step it chooses."""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from repo2ree_testbed.records import Record

FAULTS_URL = "E2E_FAULTS_URL"


class KillWorkbench(Record):
    kind: Literal["kill_workbench"] = "kill_workbench"
    allocation_id: str


class PauseWorkbench(Record):
    kind: Literal["pause_workbench"] = "pause_workbench"
    allocation_id: str


class ResumeWorkbench(Record):
    kind: Literal["resume_workbench"] = "resume_workbench"
    allocation_id: str


class PartitionWorkbench(Record):
    kind: Literal["partition_workbench"] = "partition_workbench"
    allocation_id: str


class HealWorkbench(Record):
    kind: Literal["heal_workbench"] = "heal_workbench"
    allocation_id: str


class CrashApi(Record):
    kind: Literal["crash_api"] = "crash_api"


class MisdirectProviders(Record):
    kind: Literal["misdirect_providers"] = "misdirect_providers"


class RestoreProviders(Record):
    kind: Literal["restore_providers"] = "restore_providers"


type Fault = Annotated[
    KillWorkbench
    | PauseWorkbench
    | ResumeWorkbench
    | PartitionWorkbench
    | HealWorkbench
    | CrashApi
    | MisdirectProviders
    | RestoreProviders,
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

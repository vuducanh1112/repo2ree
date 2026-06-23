"""Stateless projection of a runtime substrate into its exact command lifecycle.

The frontend shows *what will actually run* when a substrate is selected. Rather
than mirror the backend's command-building by hand (which would drift), it asks
this endpoint, which delegates to the same core builders the executors use.

This needs no workbench and no run: the plan is a pure function of the
:class:`EnvEntry` (substrate kind + declared params).
"""

from __future__ import annotations

from fastapi import APIRouter

from repo2ree_core.domain.env_entry import EnvEntry
from repo2ree_core.working_environment.command_plan import CommandPlan, describe_plan

runtime_plan_router = APIRouter()


@runtime_plan_router.post("/api/v1/runtime/command-plan")
def runtime_command_plan_route(entry: EnvEntry) -> CommandPlan:
    """Return the exact pre/exec/post command lifecycle for *entry*."""
    return describe_plan(entry)

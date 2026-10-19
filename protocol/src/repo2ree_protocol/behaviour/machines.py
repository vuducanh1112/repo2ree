"""Behaviour machines and boundaries, generated from specifications/behaviour. Do not edit.

Regenerate with ``python -m repo2ree_conformance generate``; a test fails while this
module disagrees with the specification it was generated from.
"""

from __future__ import annotations

from repo2ree_protocol.behaviour.model import BoundaryShape, MachineShape

SPEC_DIGEST = "sha256:1eaaf8f051595b63be721fad378339209cad47c76e07bc695ceab8c3ed464532"

MACHINES: dict[str, MachineShape] = {
    "Allocation": MachineShape(
        name="Allocation",
        owner="supervisor",
        initial=frozenset(
            {
                "requested",
            }
        ),
        states=(
            "requested",
            "provisioning",
            "waiting_for_workbench",
            "ready",
            "assigned",
            "draining",
            "released",
            "failed",
            "lost",
        ),
        terminal=frozenset(
            {
                "released",
            }
        ),
        facts=frozenset(
            {
                "detail",
                "location_id",
                "provider_id",
                "workbench_id",
            }
        ),
        edges={
            "requested": frozenset(
                {
                    "draining",
                    "failed",
                    "provisioning",
                    "waiting_for_workbench",
                }
            ),
            "provisioning": frozenset(
                {
                    "draining",
                    "failed",
                    "lost",
                    "waiting_for_workbench",
                }
            ),
            "waiting_for_workbench": frozenset(
                {
                    "draining",
                    "failed",
                    "lost",
                    "ready",
                }
            ),
            "ready": frozenset(
                {
                    "assigned",
                    "draining",
                    "failed",
                    "lost",
                }
            ),
            "assigned": frozenset(
                {
                    "draining",
                    "failed",
                    "lost",
                }
            ),
            "draining": frozenset(
                {
                    "failed",
                    "released",
                }
            ),
            "released": frozenset(),
            "failed": frozenset(
                {
                    "draining",
                }
            ),
            "lost": frozenset(
                {
                    "draining",
                }
            ),
        },
    ),
    "Attempt": MachineShape(
        name="Attempt",
        owner="core",
        initial=frozenset(
            {
                "pending",
            }
        ),
        states=(
            "pending",
            "executing",
            "completed",
            "captured",
            "capture_failed",
        ),
        terminal=frozenset(
            {
                "capture_failed",
                "captured",
            }
        ),
        facts=frozenset(
            {
                "changed",
                "commit",
                "dispatched_by",
                "error",
                "operation",
                "outcome",
                "run_id",
                "scope",
            }
        ),
        edges={
            "pending": frozenset(
                {
                    "capture_failed",
                    "executing",
                }
            ),
            "executing": frozenset(
                {
                    "capture_failed",
                    "completed",
                }
            ),
            "completed": frozenset(
                {
                    "capture_failed",
                    "captured",
                }
            ),
            "captured": frozenset(),
            "capture_failed": frozenset(),
        },
    ),
    "Ree": MachineShape(
        name="Ree",
        owner="core",
        initial=frozenset(
            {
                "draft",
                "sealed",
            }
        ),
        states=(
            "draft",
            "sealed",
        ),
        terminal=frozenset(
            {
                "sealed",
            }
        ),
        facts=frozenset(
            {
                "attempt_id",
                "cause",
                "commit",
                "operation",
            }
        ),
        edges={
            "draft": frozenset(
                {
                    "draft",
                    "sealed",
                }
            ),
            "sealed": frozenset(),
        },
    ),
    "Run": MachineShape(
        name="Run",
        owner="api",
        initial=frozenset(
            {
                "queued",
            }
        ),
        states=(
            "queued",
            "provisioning",
            "running",
            "canceling",
            "succeeded",
            "failed",
            "canceled",
        ),
        terminal=frozenset(
            {
                "canceled",
                "failed",
                "succeeded",
            }
        ),
        facts=frozenset(
            {
                "attempt_id",
                "failure_category",
                "operation",
            }
        ),
        edges={
            "queued": frozenset(
                {
                    "canceling",
                    "failed",
                    "provisioning",
                    "running",
                }
            ),
            "provisioning": frozenset(
                {
                    "canceled",
                    "canceling",
                    "failed",
                    "succeeded",
                }
            ),
            "running": frozenset(
                {
                    "canceled",
                    "canceling",
                    "failed",
                    "succeeded",
                }
            ),
            "canceling": frozenset(
                {
                    "canceled",
                    "failed",
                    "succeeded",
                }
            ),
            "succeeded": frozenset(),
            "failed": frozenset(),
            "canceled": frozenset(),
        },
    ),
    "Step": MachineShape(
        name="Step",
        owner="core",
        initial=frozenset(
            {
                "current",
                "missing",
                "not_applicable",
                "stale",
            }
        ),
        states=(
            "missing",
            "current",
            "stale",
            "not_applicable",
        ),
        terminal=frozenset(),
        facts=frozenset(
            {
                "attempt_id",
                "cause",
                "kind",
                "operation",
                "step",
            }
        ),
        edges={
            "missing": frozenset(
                {
                    "current",
                    "not_applicable",
                    "stale",
                }
            ),
            "current": frozenset(
                {
                    "missing",
                    "not_applicable",
                    "stale",
                }
            ),
            "stale": frozenset(
                {
                    "current",
                    "missing",
                    "not_applicable",
                }
            ),
            "not_applicable": frozenset(
                {
                    "current",
                    "missing",
                    "stale",
                }
            ),
        },
    ),
}

BOUNDARIES: dict[str, BoundaryShape] = {
    "dispatch": BoundaryShape(
        name="dispatch",
        sender="supervisor",
        request="exec_action",
        responses=frozenset(
            {
                "error",
                "result",
                "unavailable",
            }
        ),
    ),
}

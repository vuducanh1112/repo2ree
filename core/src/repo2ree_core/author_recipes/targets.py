"""Resolve shared inference and lint selectors to reserved script paths."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)
from repo2ree_protocol.command import TargetKind


class ScriptTargetSelector(BaseModel):
    """A script kind whose reserved path is resolved server-side."""

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    experiment_name: str | None = None


class ScriptTarget(BaseModel):
    """A resolved executable target. ``path`` is output-only."""

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    experiment_name: str | None = None
    path: str


def resolve_target(selector: ScriptTargetSelector) -> ScriptTarget:
    """Resolve a selector, rejecting misplaced or missing experiment names."""
    kind = selector.kind
    name = selector.experiment_name
    if kind in ("experiment_run", "experiment_verify"):
        if not name:
            raise ValueError(f"{kind} requires an experiment_name")
        path = experiment_run_script_path(name) if kind == "experiment_run" else experiment_verify_script_path(name)
        return ScriptTarget(kind=kind, experiment_name=name, path=path)

    if name:
        raise ValueError(f"{kind} must not carry an experiment_name")
    path = {
        "build": RESERVED_BUILD_SCRIPT,
        "activation_run": RESERVED_ACTIVATION_SCRIPT,
        "activation_verify": RESERVED_ACTIVATION_VERIFY_SCRIPT,
    }[kind]
    return ScriptTarget(kind=kind, path=path)


__all__ = ["ScriptTarget", "ScriptTargetSelector", "resolve_target"]

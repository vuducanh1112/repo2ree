"""Pure resolution rules for starting a runnable — the single source of truth.

Both consumers of core apply these rules: the API preflight (host-side, for a
synchronous 4xx before a run is created) and the in-workbench handlers
(authoritative — the intent can change between preflight and dispatch, so the
preflight is advisory). Keeping the rules in one function is what stops the
two sides drifting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from repo2ree_core.experiment.experiment import Activation, Experiment

if TYPE_CHECKING:
    # Type-only: ree_intent imports this package, so a runtime import here
    # would be circular.
    from repo2ree_core.domain.ree_intent import ReeIntent


class RunnableResolutionError(ValueError):
    """The intent cannot produce this runnable in its current state."""


class ExperimentNotFoundError(RunnableResolutionError):
    """No experiment with the requested name exists on the intent."""


class RunnableNotReadyError(RunnableResolutionError):
    """The runnable exists but is missing something it needs to run."""


def resolve_experiment_runnable(intent: ReeIntent, name: str) -> Experiment:
    """Return the named experiment iff the intent can run it right now.

    Raises :class:`ExperimentNotFoundError` or :class:`RunnableNotReadyError`
    with a user-facing message otherwise. A declared runtime artifact is *not*
    required: run scripts are self-contained and may run natively. When one is
    declared, its digest is bound into the run receipt; when not, the receipt
    simply carries no runtime binding.
    """
    experiment = next((exp for exp in intent.experiments if exp.name == name), None)
    if experiment is None:
        raise ExperimentNotFoundError(f"Experiment {name!r} not found")
    if not experiment.run_script.strip():
        raise RunnableNotReadyError("Experiment has no run script")
    return experiment


def resolve_activation_runnable(intent: ReeIntent) -> Activation:
    """Return the activation iff the intent can run it right now."""
    if not intent.activation.run_script.strip():
        raise RunnableNotReadyError("Activation has no run script")
    return intent.activation

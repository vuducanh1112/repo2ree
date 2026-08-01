"""Pure resolution rules for starting a runnable — the single source of truth.

The in-workbench handlers are the only consumer: they read the intent from the
workbench itself, so their verdict is authoritative. The API deliberately does
not pre-check these rules host-side — that would cost a round-trip into the
workbench on the click path for an answer the intent could invalidate before
dispatch anyway. An unresolvable runnable surfaces as a failed run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from repo2ree_core.domain.experiment import Activation, Experiment

if TYPE_CHECKING:
    # Type-only: ree_intent imports this package, so a runtime import here
    # would be circular.
    from repo2ree_core.domain.ree.intent import ReeIntent


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

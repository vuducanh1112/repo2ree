"""The shared runnable-resolution rules (single source of truth for preflight
and the in-workbench handlers)."""

from __future__ import annotations

import pytest

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.execution.experiment.resolve import (
    ExperimentNotFoundError,
    RunnableNotReadyError,
    resolve_activation_runnable,
    resolve_experiment_runnable,
)


def _intent(**overrides: object) -> ReeIntent:
    payload: dict[str, object] = {
        "runtime": "runtime.tar",
        "experiments": [{"name": "exp-a", "run_script": "ree-scripts/experiments/exp-a.sh"}],
    }
    payload.update(overrides)
    return ReeIntent.model_validate(payload)


class TestResolveExperimentRunnable:
    def test_returns_the_named_experiment(self) -> None:
        experiment = resolve_experiment_runnable(_intent(), "exp-a")
        assert experiment.name == "exp-a"

    def test_does_not_require_a_runtime(self) -> None:
        # Run scripts are self-contained and may run natively; a declared
        # runtime is bound into the receipt when present, never required.
        experiment = resolve_experiment_runnable(_intent(runtime=""), "exp-a")
        assert experiment.name == "exp-a"

    def test_unknown_name_is_not_found(self) -> None:
        with pytest.raises(ExperimentNotFoundError, match="'exp-b' not found"):
            resolve_experiment_runnable(_intent(), "exp-b")

    def test_requires_a_run_script(self) -> None:
        # A *named* experiment always has its run script settled by the model,
        # so the only reachable empty-script state is an unnamed draft.
        intent = _intent(experiments=[{"name": "", "run_script": ""}])
        with pytest.raises(RunnableNotReadyError, match="no run script"):
            resolve_experiment_runnable(intent, "")


class TestResolveActivationRunnable:
    def test_returns_the_activation(self) -> None:
        intent = _intent(activation={"run_script": "ree-scripts/activate.sh"})
        assert resolve_activation_runnable(intent) is intent.activation

    def test_requires_a_run_script(self) -> None:
        # The model normalizes an empty activation script back to the reserved
        # path, so bypass validation to exercise the defense-in-depth guard.
        intent = _intent()
        intent.activation.run_script = ""
        with pytest.raises(RunnableNotReadyError, match="Activation has no run script"):
            resolve_activation_runnable(intent)

    def test_does_not_require_a_runtime(self) -> None:
        intent = _intent(runtime="", activation={"run_script": "ree-scripts/activate.sh"})
        assert resolve_activation_runnable(intent).run_script == "ree-scripts/activate.sh"

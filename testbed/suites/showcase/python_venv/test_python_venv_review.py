"""A reviewer reproduces a pip venv runtime's experiment."""

from __future__ import annotations

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import PYTHON_VENV

F = PYTHON_VENV


def test_a_reviewer_reproduces_the_experiment_in_the_venv(client: Client, new_ree: NewRee) -> None:
    reproduction = client.reproduced(new_ree, F)

    assert "Pandas Hello World" in reproduction.logs
    assert [(item.experiment_name, item.verdict) for item in reproduction.review.experiment_comparisons] == [
        (F.experiment, F.verdict)
    ]

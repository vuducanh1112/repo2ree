"""A reviewer rebuilds the conda environment from its file, activates it, and gets the author's result."""

from __future__ import annotations

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import CONDA

F = CONDA


def test_a_reviewer_rebuilds_the_environment_and_reproduces_the_result(client: Client, new_ree: NewRee) -> None:
    review = client.reproduced(new_ree, F).review

    assert review.build_comparison is not None
    assert review.build_comparison.basis == "independent"
    assert [(item.experiment_name, item.verdict) for item in review.experiment_comparisons] == [
        (F.experiment, F.verdict)
    ]

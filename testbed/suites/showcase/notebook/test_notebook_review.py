"""A reviewer reruns the notebook: its numbers and figure hold, and the run times it records keep it from identical."""

from __future__ import annotations

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import NOTEBOOK

F = NOTEBOOK


def test_a_reviewer_reruns_the_notebook_and_the_result_is_reproduced(client: Client, new_ree: NewRee) -> None:
    reproduction = client.reproduced(new_ree, F)

    assert "rate: 0.1735 per hour" in reproduction.logs
    [comparison] = reproduction.review.experiment_comparisons
    assert comparison.verdict == F.verdict
    assert comparison.observed_verify_exit_code == 0
    assert comparison.expected_output_digest != comparison.observed_output_digest

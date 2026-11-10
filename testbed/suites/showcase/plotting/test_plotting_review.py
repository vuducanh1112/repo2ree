"""A reviewer's rebuild from hash-pinned wheels draws the author's figure again, byte for byte."""

from __future__ import annotations

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import PLOTTING

F = PLOTTING


def test_a_reviewer_redraws_the_figure_and_the_outputs_are_identical(client: Client, new_ree: NewRee) -> None:
    [comparison] = client.reproduced(new_ree, F).review.experiment_comparisons

    assert comparison.verdict == F.verdict
    assert comparison.observed_verify_exit_code == 0
    assert comparison.expected_output_digest == comparison.observed_output_digest

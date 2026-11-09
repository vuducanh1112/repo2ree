"""An experiment whose output changes on every run: the author's criterion decides, not the digits."""

from __future__ import annotations

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import STOCHASTIC

F = STOCHASTIC


def test_a_reviewer_gets_other_digits_and_the_result_is_reproduced_not_identical(
    client: Client, new_ree: NewRee
) -> None:
    [comparison] = client.reproduced(new_ree, F).review.experiment_comparisons

    assert comparison.verdict == F.verdict
    assert comparison.observed_verify_exit_code == 0
    assert comparison.expected_output_digest != comparison.observed_output_digest

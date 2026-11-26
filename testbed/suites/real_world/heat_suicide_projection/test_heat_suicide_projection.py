from __future__ import annotations

from cli_client import CliClient
from journey import author_seal_and_review
from typed_client import NewRee

from repo2ree_testbed.showcases import HEAT_SUICIDE_PROJECTION


def test_every_stage_of_the_capsule_regenerates_its_results_from_the_observed_data_and_a_review_reproduces_them(
    client: CliClient, new_ree: NewRee, reviewer: CliClient, new_reviewer_ree: NewRee
) -> None:
    reviewed = author_seal_and_review(
        client,
        new_ree,
        reviewer,
        new_reviewer_ree,
        HEAT_SUICIDE_PROJECTION,
        "Code Ocean capsule of Projections of temperature-related suicide mortality under climate change: "
        "A multi-country time-series study.",
    )
    assert reviewed.lfs_files == (), "the capsule keeps its data in git itself"
    assert reviewed.verdicts == {HEAT_SUICIDE_PROJECTION.experiment: HEAT_SUICIDE_PROJECTION.verdict}, (
        "its figures carry the time they were drawn: only the verify can agree"
    )

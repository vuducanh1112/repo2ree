from __future__ import annotations

from cli_client import CliClient
from journey import author_seal_and_review
from typed_client import NewRee

from repo2ree_testbed.showcases import TRR341_DROUGHT_CAMELINA


def test_each_workflow_of_the_arc_and_all_of_them_reproduce_from_the_data_it_keeps_in_lfs(
    client: CliClient, new_ree: NewRee, reviewer: CliClient, new_reviewer_ree: NewRee
) -> None:
    reviewed = author_seal_and_review(
        client,
        new_ree,
        reviewer,
        new_reviewer_ree,
        TRR341_DROUGHT_CAMELINA,
        "ARC of Drought responses reshape growth, reproduction and seed traits in Camelina sativa.",
    )
    assert len(reviewed.lfs_files) == 21, "the assays' data, the runs' models and figures, all from Git LFS"
    assert reviewed.verdicts == {
        experiment.name: experiment.verdict for experiment in TRR341_DROUGHT_CAMELINA.experiments
    }, "a workflow that draws or keeps its models stamps them anew: only its verify can agree"

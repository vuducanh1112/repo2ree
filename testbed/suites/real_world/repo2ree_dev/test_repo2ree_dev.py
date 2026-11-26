from __future__ import annotations

from cli_client import CliClient
from journey import author_seal_and_review
from typed_client import NewRee

from repo2ree_testbed.showcases import REPO2REE_DEV


def test_the_dev_environment_passes_the_commit_gate_and_a_review_reproduces_it(
    client: CliClient, new_ree: NewRee, reviewer: CliClient, new_reviewer_ree: NewRee
) -> None:
    reviewed = author_seal_and_review(
        client, new_ree, reviewer, new_reviewer_ree, REPO2REE_DEV, "The repo2ree dev environment."
    )
    assert reviewed.lfs_files == ()
    assert reviewed.verdicts == {REPO2REE_DEV.experiment: REPO2REE_DEV.verdict}, (
        "the gate's receipt holds when it was written: only the verify can agree"
    )

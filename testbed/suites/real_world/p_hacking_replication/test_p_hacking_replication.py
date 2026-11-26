from __future__ import annotations

from cli_client import CliClient
from journey import author_seal_and_review
from typed_client import NewRee

from repo2ree_testbed.showcases import P_HACKING_REPLICATION


def test_the_replication_package_regenerates_its_tables_and_a_review_reproduces_them(
    client: CliClient, new_ree: NewRee, reviewer: CliClient, new_reviewer_ree: NewRee
) -> None:
    reviewed = author_seal_and_review(
        client,
        new_ree,
        reviewer,
        new_reviewer_ree,
        P_HACKING_REPLICATION,
        "Replication package of p-Hacking and Publication Bias in Design-Based Causal Studies in Information Systems.",
    )
    assert reviewed.lfs_files == ()
    assert reviewed.verdicts == {P_HACKING_REPLICATION.experiment: P_HACKING_REPLICATION.verdict}, (
        "its spreadsheets and PDFs hold when they were written: only the verify can agree"
    )

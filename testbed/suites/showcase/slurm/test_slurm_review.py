"""A reviewer on the cluster reproduces the experiment through the author's launch, as a Slurm job step."""

from __future__ import annotations

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import SLURM

F = SLURM


def test_a_reviewer_on_the_cluster_reproduces_the_experiment_as_a_job(client: Client, new_ree: NewRee) -> None:
    reproduction = client.reproduced(new_ree, F)

    [receipt] = reproduction.review.experiment_receipts
    assert receipt.launched is not None
    assert receipt.launched.slurm_job_id is not None
    assert [(item.experiment_name, item.verdict) for item in reproduction.review.experiment_comparisons] == [
        (F.experiment, F.verdict)
    ]

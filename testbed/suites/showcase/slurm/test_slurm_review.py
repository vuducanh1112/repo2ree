"""An REE whose author's scripts submit their work to Slurm, which the product runs like any other script."""

from __future__ import annotations

import re

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import SLURM

F = SLURM


def test_a_reviewer_on_the_cluster_reproduces_the_experiment_as_a_job(client: Client, new_ree: NewRee) -> None:
    reproduction = client.reproduced(new_ree, F)

    assert re.search(r"ran in Slurm job \d+", reproduction.logs)
    assert [(item.experiment_name, item.verdict) for item in reproduction.review.experiment_comparisons] == [
        (F.experiment, F.verdict)
    ]

"""An REE whose Containerfile is built and run with rootless Podman, on a machine whose scripts can use only Podman."""

from __future__ import annotations

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import PODMAN

F = PODMAN


def test_a_reviewer_rebuilds_the_containerfile_with_podman_and_reproduces_the_result(
    client: Client, new_ree: NewRee
) -> None:
    reproduction = client.reproduced(new_ree, F)

    assert "--- Podman Hello World ---" in reproduction.logs
    assert [(item.experiment_name, item.verdict) for item in reproduction.review.experiment_comparisons] == [
        (F.experiment, F.verdict)
    ]

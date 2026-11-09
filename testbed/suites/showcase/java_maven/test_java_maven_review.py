"""A reviewer reproduces a Maven project's experiment in its saved image."""

from __future__ import annotations

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import JAVA_MAVEN

F = JAVA_MAVEN


def test_a_reviewer_reproduces_the_experiment_on_the_jvm(client: Client, new_ree: NewRee) -> None:
    reproduction = client.reproduced(new_ree, F)

    assert '"greeting": "Hello"' in reproduction.logs
    assert [(item.experiment_name, item.verdict) for item in reproduction.review.experiment_comparisons] == [
        (F.experiment, F.verdict)
    ]

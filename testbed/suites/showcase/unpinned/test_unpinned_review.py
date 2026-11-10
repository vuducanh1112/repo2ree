"""Upstream releases after the seal: a rebuild does not reproduce the result, the sealed experiment environment does."""

from __future__ import annotations

from typed_client import Client, NewRee
from upstream_release import author, publish

from repo2ree_testbed.api_models import Review, ReviewBasis
from repo2ree_testbed.showcases import UNPINNED

F = UNPINNED


def reviewed(client: Client, reviewer: str, build: ReviewBasis) -> Review:
    """One review attempt, end to end, with the experiment environment from ``build``."""
    before = {review.review_id for review in client.reviews(reviewer)}
    source = client.review_source(reviewer, "auto", watch=F.watch)
    assert source.status == "succeeded", client.logs(reviewer, source)
    [review_id] = [review.review_id for review in client.reviews(reviewer) if review.review_id not in before]

    experiment_environment = client.review_build_experiment_environment(reviewer, review_id, build, watch=F.watch)
    assert experiment_environment.status == "succeeded", client.logs(reviewer, experiment_environment)
    activation = client.review_activation(reviewer, review_id, watch=F.watch)
    assert activation.status == "succeeded", client.logs(reviewer, activation)
    experiment = client.review_experiment(reviewer, review_id, F.experiment, watch=F.watch)
    assert experiment.status == "succeeded", client.logs(reviewer, experiment)
    review: Review = client.review(reviewer, review_id)
    return review


def test_a_rebuild_after_an_upstream_release_is_different_and_the_sealed_experiment_environment_reproduces(
    client: Client, new_ree: NewRee
) -> None:
    publish(F, "1.0")
    authored = new_ree("review-author", image=F.image)
    author(client, authored, F)
    assert client.seal(authored, watch=F.watch).status == "succeeded"
    archive = client.archive(authored, "review-baseline")

    publish(F, "2.0")

    reviewer = new_ree("reviewer", image=F.image)
    client.load(reviewer, archive.read_bytes())

    rebuilt = reviewed(client, reviewer, "auto")
    assert rebuilt.experiment_environment_comparison is not None
    assert rebuilt.experiment_environment_comparison.basis == "independent"
    [comparison] = rebuilt.experiment_comparisons
    assert comparison.verdict == F.verdict
    assert comparison.observed_verify_exit_code not in (None, 0)

    sealed = reviewed(client, reviewer, "bundled")
    assert sealed.experiment_environment_comparison is not None
    assert sealed.experiment_environment_comparison.basis == "bundled"
    assert [(item.experiment_name, item.verdict) for item in sealed.experiment_comparisons] == [
        (F.experiment, "identical")
    ]

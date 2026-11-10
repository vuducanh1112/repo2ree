"""The reviewer lifecycle against an REE this suite did not author, the bundle the GUI's review showcase starts from."""

from __future__ import annotations

from system_client import ROOT
from typed_client import Client, NewRee

from repo2ree_testbed.showcases import PYTHON_DOCKER

F = PYTHON_DOCKER
BUNDLE = ROOT / "examples/rees/ree-hello-world.zip"


def test_a_reviewer_reproduces_another_authors_source_experiment_environment_activation_and_result(
    client: Client, new_ree: NewRee
) -> None:
    reviewer = new_ree("reviewer", image=F.image)
    client.load(reviewer, BUNDLE.read_bytes())

    refused = client.review_source(reviewer, "independent", watch=F.watch)
    assert refused.status == "failed", "the bundle's source was uploaded: it has no origin to fetch"

    source = client.review_source(reviewer, "bundled", watch=F.watch)
    assert source.status == "succeeded", client.logs(reviewer, source)
    settled = [item for item in client.reviews(reviewer) if item.source_comparison is not None]
    assert [
        (item.source_comparison.basis, item.source_comparison.verdict) for item in settled if item.source_comparison
    ] == [("bundled", "identical")]
    review_id = settled[0].review_id

    build = client.review_build_experiment_environment(reviewer, review_id, "auto", watch=F.watch)
    assert build.status == "succeeded", client.logs(reviewer, build)
    comparison = client.review(reviewer, review_id).experiment_environment_comparison
    assert comparison is not None
    assert comparison.verdict in {"identical", "equivalent", "different"}
    assert comparison.basis == "independent", "the bundle ships no experiment environment: only a rebuild can answer"
    assert (comparison.missing_count, comparison.extra_count) == (0, 0)

    activation = client.review_activation(reviewer, review_id, watch=F.watch)
    assert activation.status == "succeeded", client.logs(reviewer, activation)

    experiment = client.review_experiment(reviewer, review_id, F.experiment, watch=F.watch)
    assert experiment.status == "succeeded", client.logs(reviewer, experiment)
    review = client.review(reviewer, review_id)
    assert [(item.experiment_name, item.verdict) for item in review.experiment_comparisons] == [
        (F.experiment, F.verdict)
    ]

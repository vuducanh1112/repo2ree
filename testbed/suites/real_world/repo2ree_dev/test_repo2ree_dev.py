from __future__ import annotations

from cli_client import CliClient
from typed_client import NewRee

from repo2ree_testbed.showcases import REPO2REE_DEV

F = REPO2REE_DEV


def test_the_dev_environment_passes_the_commit_gate_and_a_review_reproduces_it(
    client: CliClient, new_ree: NewRee
) -> None:
    assert F.origin is not None
    ree_id = new_ree("repo2ree-dev")

    fetched = client.fetch_source(ree_id, F.origin.url, "git", F.origin.revision)
    assert fetched.status == "succeeded", client.logs(ree_id, fetched)
    source = client.ree(ree_id).subject.receipts.acquire_source
    assert source is not None
    assert (source.resolved_revision, source.history) == (F.origin.revision, "full")

    client.declare_name(ree_id, "repo2ree-dev")
    client.declare_catalog(ree_id, version=F.origin.revision[:8], description="The repo2ree dev environment.")
    client.observe_hardware(ree_id)
    for label, step in (
        ("evaluation", lambda: client.evaluate(ree_id)),
        ("build", lambda: client.build_experiment_environment(ree_id, F)),
        ("SBOM", lambda: client.generate_sbom(ree_id)),
        ("SBOM cross-check", lambda: client.cross_check_sbom(ree_id)),
        ("activation", lambda: client.activate(ree_id, F)),
        ("commit gate", lambda: client.run_experiment(ree_id, F)),
        ("seal", lambda: client.seal(ree_id, experiment_environment_included=False)),
    ):
        run = step()
        assert run.status == "succeeded", f"{label} ended {run.status}\n{client.logs(ree_id, run)}"

    acquired = client.review_acquire_source(ree_id, "independent")
    assert acquired.status == "succeeded", client.logs(ree_id, acquired)
    [review] = client.reviews(ree_id)
    assert review.source_comparison is not None
    assert review.source_comparison.verdict == "identical"
    assert review.source_comparison.observed_revision == F.origin.revision

    for label, step in (
        ("review build", lambda: client.review_build_experiment_environment(ree_id, review.review_id, "independent")),
        ("review activation", lambda: client.review_activate_experiment_environment(ree_id, review.review_id)),
        ("review commit gate", lambda: client.review_run_experiment(ree_id, review.review_id, F.experiment)),
    ):
        run = step()
        assert run.status == "succeeded", f"{label} ended {run.status}\n{client.logs(ree_id, run)}"

    [experiment] = client.review(ree_id, review.review_id).experiment_comparisons
    assert experiment.verdict == F.verdict, "the gate's receipt holds when it was written: only the verify can agree"

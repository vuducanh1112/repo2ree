from __future__ import annotations

from dataclasses import dataclass

from cli_client import CliClient
from typed_client import NewRee

from repo2ree_testbed.api_models import ExperimentComparison, LfsFile
from repo2ree_testbed.showcases import Project


@dataclass(frozen=True)
class Reviewed:
    experiments: dict[str, ExperimentComparison]
    lfs_files: tuple[LfsFile, ...]

    @property
    def verdicts(self) -> dict[str, str]:
        return {name: comparison.verdict for name, comparison in self.experiments.items()}


def author_seal_and_review(
    author: CliClient,
    new_ree: NewRee,
    reviewer: CliClient,
    new_reviewer_ree: NewRee,
    project: Project,
    description: str,
) -> Reviewed:
    assert project.origin is not None
    assert reviewer.machine.container != author.machine.container, "the review runs on a machine of its own"
    name = project.name.replace("_", "-")
    ree_id = new_ree(name)

    fetched = author.fetch_source(ree_id, project.origin.url, "git", project.origin.revision)
    assert fetched.status == "succeeded", author.logs(ree_id, fetched)
    source = author.ree(ree_id).subject.receipts.acquire_source
    assert source is not None
    assert (source.resolved_revision, source.history) == (project.origin.revision, "full")
    lfs_files = source.lfs_files

    author.declare_name(ree_id, name)
    author.declare_catalog(ree_id, version=project.origin.revision[:8], description=description)
    author.observe_hardware(ree_id)
    for label, step in (
        ("evaluation", lambda: author.evaluate(ree_id)),
        ("build", lambda: author.build_experiment_environment(ree_id, project)),
        ("SBOM", lambda: author.generate_sbom(ree_id)),
        ("SBOM cross-check", lambda: author.cross_check_sbom(ree_id)),
        ("activation", lambda: author.activate(ree_id, project)),
    ):
        run = step()
        assert run.status == "succeeded", f"{label} ended {run.status}\n{author.logs(ree_id, run)}"
    for experiment in project.experiments:
        run = author.run_experiment(ree_id, project, experiment)
        assert run.status == "succeeded", f"experiment {experiment.name} ended {run.status}\n{author.logs(ree_id, run)}"
    sealing = author.seal(ree_id, experiment_environment_included=False)
    assert sealing.status == "succeeded", f"seal ended {sealing.status}\n{author.logs(ree_id, sealing)}"
    sealed = author.archive(ree_id, "sealed")

    reviewed = new_reviewer_ree(f"{name}-review")
    reviewer.load(reviewed, sealed.read_bytes())
    acquired = reviewer.review_acquire_source(reviewed, "independent")
    assert acquired.status == "succeeded", reviewer.logs(reviewed, acquired)
    [review] = reviewer.reviews(reviewed)
    assert review.source_comparison is not None
    assert review.source_comparison.verdict == "identical"
    assert review.source_comparison.observed_revision == project.origin.revision
    assert review.source_comparison.lfs_failure is None
    assert review.receipts.acquire_source is not None
    assert review.receipts.acquire_source.lfs_files == lfs_files, "the review fetched the same LFS content"

    for label, step in (
        (
            "review build",
            lambda: reviewer.review_build_experiment_environment(reviewed, review.review_id, "independent"),
        ),
        ("review activation", lambda: reviewer.review_activate_experiment_environment(reviewed, review.review_id)),
    ):
        run = step()
        assert run.status == "succeeded", f"{label} ended {run.status}\n{reviewer.logs(reviewed, run)}"
    for experiment in project.experiments:
        run = reviewer.review_run_experiment(reviewed, review.review_id, experiment.name)
        assert run.status == "succeeded", (
            f"review experiment {experiment.name} ended {run.status}\n{reviewer.logs(reviewed, run)}"
        )

    comparisons = reviewer.review(reviewed, review.review_id).experiment_comparisons
    return Reviewed({comparison.experiment_name: comparison for comparison in comparisons}, lfs_files)

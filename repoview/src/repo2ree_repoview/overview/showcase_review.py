"""The review a showcase's review test left, read from the copy the test preserved.

A review is a Git repository of its own inside the reviewer's REE (``ree/reviews/<review id>``), and its
``review.json`` at the last commit is its report: what it reviewed, on which machine, each step's state, and its
verdicts on the source, the experiment environment, the activation and each experiment.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from repo2ree_repoview.documents import Document

REVIEWS = "reviews"
REPORT = "review.json"
SIGNATURE = "signatures/review.sigstore.json"

ReviewStatus = Literal["running", "completed", "failed", "canceled"]
Basis = Literal["independent", "bundled"]
SourceVerdict = Literal["identical", "different", "inconclusive"]
EnvironmentVerdict = Literal["identical", "equivalent", "different", "inconclusive"]
ActivationVerdict = Literal["passed", "failed"]
ExperimentVerdict = Literal["identical", "reproduced", "different", "inconclusive"]
Verdict = SourceVerdict | EnvironmentVerdict | ActivationVerdict | ExperimentVerdict


class ReviewSubject(Document):
    name: str
    version: str = ""
    ree_digest: str | None = None
    experiments: tuple[str, ...] = ()


class ReviewMachine(Document):
    system: str
    architecture: str


class ReviewStep(Document):
    step: str
    status: ReviewStatus
    failure: str | None = None


class SourceComparison(Document):
    basis: Basis
    verdict: SourceVerdict
    expected_swhid: str | None = None
    observed_swhid: str | None = None


class PackageDelta(Document):
    ecosystem: str
    name: str
    expected_version: str | None = None
    observed_version: str | None = None


class EnvironmentComparison(Document):
    basis: Basis
    verdict: EnvironmentVerdict
    expected_artifact_digest: str | None = None
    observed_artifact_digest: str | None = None
    expected_package_total: int = 0
    observed_package_total: int = 0
    matched: int = 0
    missing_count: int = 0
    extra_count: int = 0
    version_mismatch_count: int = 0
    advisory_count: int = 0
    missing: tuple[PackageDelta, ...] = ()
    extra: tuple[PackageDelta, ...] = ()
    version_mismatches: tuple[PackageDelta, ...] = ()


class ActivationOutcome(Document):
    basis: Basis
    verdict: ActivationVerdict
    exit_code: int | None = None


class ExperimentComparison(Document):
    experiment_name: str
    basis: Basis
    verdict: ExperimentVerdict
    verify_script_path: str = ""
    expected_output_digest: str | None = None
    observed_output_digest: str | None = None
    expected_verify_exit_code: int | None = None
    observed_verify_exit_code: int | None = None


class ReviewReport(Document):
    review_id: str
    subject: ReviewSubject
    machine: ReviewMachine
    created_at: str
    updated_at: str
    status: ReviewStatus
    steps: tuple[ReviewStep, ...] = ()
    source_comparison: SourceComparison | None = None
    experiment_environment_comparison: EnvironmentComparison | None = None
    activation_outcome: ActivationOutcome | None = None
    experiment_comparisons: tuple[ExperimentComparison, ...] = ()
    failure: str | None = None


@dataclass(frozen=True)
class FinalReview:
    source: Path
    commit: str
    report: ReviewReport
    signed: bool


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def read_review(repo: Path) -> FinalReview | None:
    """The review in ``repo`` as of its last commit; None when that commit holds no report it can read."""
    try:
        commit = _git(repo, "rev-parse", "HEAD").decode().strip()
        files = set(_git(repo, "ls-tree", "-r", "--name-only", "-z", commit).decode().split("\0"))
        if REPORT not in files:
            return None
        report = ReviewReport.model_validate_json(_git(repo, "show", f"{commit}:{REPORT}"))
    except (subprocess.CalledProcessError, ValidationError):
        return None
    return FinalReview(source=repo, commit=commit, report=report, signed=SIGNATURE in files)


def preserved_review(test_directory: Path, rees: tuple[str, ...]) -> FinalReview | None:
    """The newest review in any REE a test preserved."""
    folders = [test_directory / "dossier/rees" / name / "ree" / REVIEWS for name in rees]
    repos = [repo for folder in folders if folder.is_dir() for repo in sorted(folder.iterdir())]
    found = [review for repo in repos if (repo / ".git").exists() and (review := read_review(repo)) is not None]
    return max(found, key=lambda review: review.report.updated_at, default=None)

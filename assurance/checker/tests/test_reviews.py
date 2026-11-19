"""A review's commits judged beside the sealed REE it reviews: its expectations are the author's, its observations
its own receipts', each verdict its ladder's, and its signature the review itself."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from test_documents import REE, bundle, git_source

from repo2ree_assurance_checker.check.documents import check_documents
from repo2ree_assurance_checker.evidence import CommittedFile, Evidence, Snapshot
from repo2ree_assurance_checker.files import load_spec

SEAL = "sha256:" + "5" * 64
SWHID = "swh:1:dir:" + "a" * 40
IMAGE = "sha256:" + "1" * 64
VERIFY = "sha256:" + "2" * 64
ACTIVATE = "sha256:" + "3" * 64
LAUNCH = "sha256:" + "4" * 64
OUTPUT = "sha256:" + "6" * 64
REVIEW = "https://repo2ree.org/claims/review/v1"


def author() -> dict[str, Any]:
    """The sealed REE, as its receipts record what the review expects."""
    return {
        "subject": {
            "receipts": {
                "acquire_source": {"observed_swhid": SWHID},
                "build_experiment_environment": {"produced_artifact_digest": IMAGE},
                "generate_sbom": {"sbom_digest": None},
                "experiments": {
                    "hello": {
                        "verify_script_digest": VERIFY,
                        "activate_experiment_environment_script_digest": ACTIVATE,
                        "verify_exit_code": 0,
                        "produced_output_digest": OUTPUT,
                        "launch_script_digest": LAUNCH,
                    }
                },
            }
        },
        "seal": {"ree_digest": SEAL},
    }


def review() -> dict[str, Any]:
    """A review that rebuilt the image bit for bit and reproduced the experiment's output identically."""
    return {
        "review_id": "r1",
        "subject": {"name": "demo", "ree_digest": SEAL, "experiments": ["hello"]},
        "receipts": {
            "acquire_source": {"expected_swhid": SWHID, "observed_swhid": SWHID},
            "build_experiment_environment": {"produced_artifact_digest": IMAGE},
            "activate_experiment_environment": {"exit_code": 0, "experiment_environment_digest": IMAGE},
            "experiments": [
                {
                    "experiment_name": "hello",
                    "run_exit_code": 0,
                    "verify_exit_code": 0,
                    "verify_script_digest": VERIFY,
                    "activate_experiment_environment_script_digest": ACTIVATE,
                    "produced_output_digest": OUTPUT,
                }
            ],
        },
        "source_comparison": {"verdict": "identical", "expected_swhid": SWHID, "observed_swhid": SWHID},
        "experiment_environment_comparison": {
            "verdict": "identical",
            "expected_artifact_digest": IMAGE,
            "observed_artifact_digest": IMAGE,
            "expected_sbom_digest": None,
            "expected_package_total": 3,
            "observed_package_total": 3,
            "missing_count": 0,
            "extra_count": 0,
            "version_mismatch_count": 0,
            "advisory_count": 0,
            "missing": [],
            "extra": [],
            "version_mismatches": [],
            "advisory": [],
        },
        "activation_outcome": {"verdict": "passed", "exit_code": 0, "experiment_environment_digest": IMAGE},
        "experiment_comparisons": [
            {
                "experiment_name": "hello",
                "verdict": "identical",
                "expected_verify_script_digest": VERIFY,
                "verify_script_digest": VERIFY,
                "expected_activate_experiment_environment_script_digest": ACTIVATE,
                "activate_experiment_environment_script_digest": ACTIVATE,
                "expected_launch_script_digest": LAUNCH,
                "expected_verify_exit_code": 0,
                "observed_verify_exit_code": 0,
                "run_exit_code": 0,
                "expected_output_digest": OUTPUT,
                "observed_output_digest": OUTPUT,
            }
        ],
    }


def committed(content: bytes) -> CommittedFile:
    return CommittedFile(
        digest=f"sha256:{hashlib.sha256(content).hexdigest()}", size=len(content), storage="git", content=content
    )


def findings(
    document: dict[str, Any], files: dict[str, CommittedFile] | None = None, *, beside: bool = True
) -> dict[str, Any]:
    snapshots = [
        Snapshot(
            source="git:ree/reviews/r1",
            position=1300,
            subject="Review",
            partition=REE,
            locator="git:ree/reviews/r1@c1",
            cause="operation",
            operation="review_run_experiment",
            document=document,
            files=files or {},
        )
    ]
    if beside:
        snapshots.insert(
            0,
            Snapshot(
                source="git:ree",
                position=1300,
                subject="Ree",
                partition=REE,
                locator="git:ree@c1",
                cause="operation",
                operation="seal_ree",
                document=author(),
            ),
        )
    evidence = Evidence(sources=(git_source(),), events=(), snapshots=tuple(snapshots))
    return {
        result.rule.removeprefix("document:"): (result.triggered, [f"{f.subject}: {f.reason}" for f in result.findings])
        for result in check_documents(load_spec(), evidence)
        if result.rule.startswith("document:review-")
    }


def test_a_faithful_review_holds_every_rule_and_each_judges_it() -> None:
    found = findings(review())
    assert {rule: problems for rule, (_, problems) in found.items() if problems} == {}
    assert {rule for rule, (triggered, _) in found.items() if not triggered} == {"review-signatures-are-the-review"}


def test_a_verdict_its_ladder_does_not_give_is_violated() -> None:
    document = review()
    document["source_comparison"]["observed_swhid"] = "swh:1:dir:" + "b" * 40
    document["receipts"]["acquire_source"]["observed_swhid"] = "swh:1:dir:" + "b" * 40
    document["experiment_comparisons"][0]["verdict"] = "identical"
    document["experiment_comparisons"][0]["observed_verify_exit_code"] = 1
    document["receipts"]["experiments"][0]["verify_exit_code"] = 1

    _, problems = findings(document)["review-verdicts-follow-their-ladders"]

    assert problems == [
        f"Review {REE} source_comparison: records 'identical', but its ladder gives 'different'",
        f"Review {REE} experiment_comparisons hello: records 'identical', but its ladder gives 'different'",
    ]


def test_a_closure_that_lists_more_than_it_counts_is_violated() -> None:
    document = review()
    document["experiment_environment_comparison"]["missing"] = [{"ecosystem": "pypi", "name": "numpy"}]
    sampled = review()
    sampled["experiment_environment_comparison"]["advisory_count"] = 60
    sampled["experiment_environment_comparison"]["advisory"] = [{"ecosystem": "other", "name": "a"}] * 50

    _, problems = findings(document)["review-verdicts-follow-their-ladders"]

    assert problems == [f"Review {REE} experiment_environment_comparison missing_count: counts 0, but lists 1"]
    assert findings(sampled)["review-verdicts-follow-their-ladders"][1] == [], "a list is a sample of its count"


def test_an_expectation_that_is_not_the_authors_is_violated() -> None:
    document = review()
    document["experiment_comparisons"][0]["expected_verify_script_digest"] = "sha256:" + "9" * 64

    _, problems = findings(document)["review-expectations-are-the-authors"]

    assert len(problems) == 1
    assert "expected_verify_script_digest hello" in problems[0]
    assert "receipts.experiments[$name].verify_script_digest" in problems[0]


def test_an_observation_its_receipt_did_not_record_is_violated() -> None:
    document = review()
    document["activation_outcome"]["exit_code"] = 3

    _, problems = findings(document)["review-observations-are-its-receipts"]

    assert problems == [problem for problem in problems if "activation_outcome.exit_code" in problem]
    assert len(problems) == 1


def test_an_experiment_compared_beside_a_failed_activation_is_violated() -> None:
    document = review()
    document["activation_outcome"] = {"verdict": "failed", "exit_code": 1, "experiment_environment_digest": IMAGE}
    document["receipts"]["activate_experiment_environment"]["exit_code"] = 1

    _, problems = findings(document)["review-experiments-follow-a-passed-activation"]

    assert len(problems) == 1


def test_a_review_with_no_ree_beside_it_is_unevidenced_not_violated() -> None:
    found = findings(review(), beside=False)

    for rule in ("review-names-a-seal-beside-it", "review-expectations-are-the-authors"):
        assert found[rule] == (0, []), rule


def test_a_review_s_signature_carries_the_review_as_it_stands() -> None:
    document = review()
    faithful = {"signatures/review.sigstore.json": committed(bundle(SEAL, REVIEW, predicate=document))}
    stale = copy.deepcopy(document)
    stale["experiment_comparisons"][0]["verdict"] = "reproduced"
    other = {"signatures/review.sigstore.json": committed(bundle(SEAL, REVIEW, predicate=stale))}

    assert findings(document, faithful)["review-signatures-are-the-review"] == (1, [])
    triggered, problems = findings(document, other)["review-signatures-are-the-review"]
    assert triggered == 1
    assert problems == [
        f"Review {REE} signatures/review.sigstore.json: signs another record than the review holds in this commit"
    ]

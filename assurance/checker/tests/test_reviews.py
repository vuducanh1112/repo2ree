from __future__ import annotations

import copy
import hashlib
from typing import Any

from test_documents import REE, bundle, git_source

from repo2ree_assurance_checker.check import check
from repo2ree_assurance_checker.check.aggregates import check_aggregate
from repo2ree_assurance_checker.check.documents import check_documents
from repo2ree_assurance_checker.evidence import CommittedFile, Event, Evidence, FieldChange, FileChange, Snapshot
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
            source="git:ree",
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


def test_a_closure_that_counts_otherwise_than_it_lists_is_violated() -> None:
    document = review()
    document["experiment_environment_comparison"]["missing"] = [{"ecosystem": "pypi", "name": "numpy"}]

    _, problems = findings(document)["review-verdicts-follow-their-ladders"]

    assert problems == [f"Review {REE} experiment_environment_comparison missing_count: counts 0, but lists 1"]


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


INSTANCE = f"{REE}/reviews/r1"


def moved(position: int, path: str, before: str | None, after: str | None, operation: str) -> FieldChange:
    return FieldChange(
        source="git:ree",
        position=position,
        partition=INSTANCE,
        subject="Review",
        path=path,
        before=before,
        after=after,
        operation=operation,
        cause="operation",
        locator=f"git:ree/reviews/r1@c{position // 1000}",
    )


def became(position: int, source: str | None, target: str, operation: str) -> Event:
    return Event(
        source="git:ree",
        position=position,
        kind="transition",
        owner="core",
        subject="Review",
        key="r1",
        partition=INSTANCE,
        source_state=source,
        target_state=target,
        facts={"commit": f"c{position}", "operation": operation, "attempt_id": f"a{position}", "cause": "operation"},
        locator=f"git:ree/reviews/r1@c{position // 1000}",
    )


def signature(position: int, operation: str) -> FileChange:
    return FileChange(
        source="git:ree",
        position=position,
        partition=INSTANCE,
        subject="Review",
        scope="reviews/r1/",
        path="reviews/r1/signatures/review.sigstore.json",
        before=None,
        after="b1",
        operation=operation,
        cause="operation",
        locator=f"git:ree/reviews/r1@c{position // 1000}",
        storage="git",
    )


def reviewed_history(*extra: FieldChange | Event | FileChange) -> Evidence:
    events = [
        became(2900, None, "open", "review_acquire_source"),
        became(3900, "open", "open", "review_run_experiment"),
        became(4900, "open", "signed", "sign_review"),
    ]
    changes = [
        moved(2900, "subject", None, "s1", "review_acquire_source"),
        moved(2900, "source_comparison", None, "c1", "review_acquire_source"),
        moved(3900, "experiment_comparisons", None, "e1", "review_run_experiment"),
    ]
    files = [signature(4900, "sign_review")]
    for item in extra:
        if isinstance(item, Event):
            events.append(item)
        elif isinstance(item, FieldChange):
            changes.append(item)
        else:
            files.append(item)
    return Evidence(
        sources=(git_source(),), events=tuple(events), changes=tuple(changes), files=tuple(files), snapshots=()
    )


def review_findings(evidence: Evidence) -> list[str]:
    result = check_aggregate(load_spec().aggregates["Review"], evidence)
    return [f"{finding.subject.split(' ', 2)[2]}: {finding.reason}" for finding in result.findings]


def test_a_review_s_parts_move_by_their_own_steps_and_its_signature_by_signing() -> None:
    assert review_findings(reviewed_history()) == []


def test_a_verdict_another_step_settles_violates_the_aggregate() -> None:
    wrong = moved(3900, "source_comparison", "c1", "c2", "review_run_experiment")

    assert review_findings(reviewed_history(wrong)) == [
        "source_comparison: set -> set by review_run_experiment, which no edge allows"
    ]


def test_a_signature_only_signing_adds_violates_the_aggregate_otherwise() -> None:
    added = signature(3900, "review_run_experiment")

    assert review_findings(reviewed_history(added)) == [
        "signatures/review.sigstore.json: changed by review_run_experiment, but only sign_review signs"
    ]


def test_a_signed_review_that_changes_violates_the_invariant() -> None:
    after = became(5900, "signed", "signed", "review_run_experiment")

    rules = {rule.rule: rule for rule in check(load_spec(), reviewed_history(after)).rules}

    assert rules["signed-reviews-change-no-more"].verdict == "violated"
    assert rules["signed-reviews-change-no-more"].triggered == 1

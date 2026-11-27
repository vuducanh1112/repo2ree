from __future__ import annotations

import json
import subprocess
from pathlib import Path

from repo2ree_repoview.overview.exports import Showcase, ShowcaseTest
from repo2ree_repoview.overview.pages.showcase_ree import authoring_test, page_showcase_ree, review_test
from repo2ree_repoview.overview.showcase_review import preserved_review

SOURCE = "swh:1:dir:aa"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def report(review_id: str, updated_at: str, **parts: object) -> dict[str, object]:
    return {
        "review_id": review_id,
        "subject": {"name": "author", "ree_digest": "sha256:5a", "experiments": ["hello"]},
        "machine": {"system": "Linux", "architecture": "x86_64"},
        "created_at": "2026-11-19T16:27:53Z",
        "updated_at": updated_at,
        "status": "completed",
        "steps": [
            {"step": "acquire_source", "status": "completed", "started_at": "x", "updated_at": "x"},
            {"step": "run_experiment", "status": "failed", "failure": "verify exited 1"},
        ],
        "receipts": {"acquire_source": {"run_id": "r"}},
        **parts,
    }


def review(reviews: Path, review_id: str, body: dict[str, object], *, signed: bool = False) -> None:
    repo = reviews / review_id
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    (repo / "review.json").write_text(json.dumps({**body, "status": "running"}))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "review_acquire_source")
    (repo / "review.json").write_text(json.dumps(body))
    if signed:
        (repo / "signatures").mkdir()
        (repo / "signatures/review.sigstore.json").write_text("{}")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "sign_review")


def reviewed_test(tmp_path: Path) -> Path:
    test = tmp_path / "test"
    (test / "dossier/rees/author/ree").mkdir(parents=True)
    reviews = test / "dossier/rees/reviewer/ree/reviews"
    review(reviews, "review-old", report("review-old", "2026-11-19T10:00:00Z"))
    newest = report(
        "review-new",
        "2026-11-19T16:28:31Z",
        source_comparison={
            "basis": "bundled",
            "verdict": "identical",
            "expected_swhid": SOURCE,
            "observed_swhid": SOURCE,
        },
        experiment_environment_comparison={
            "basis": "independent",
            "verdict": "inconclusive",
            "matched": 0,
            "extra_count": 1,
            "observed_package_total": 91,
            "advisory_count": 76,
            "extra": [{"ecosystem": "pypi", "name": "autocommand", "observed_version": "2.2.2"}],
            "expected_artifact_digest": "sha256:a8",
            "observed_artifact_digest": "sha256:dc",
        },
        activation_outcome={"basis": "bundled", "verdict": "passed", "exit_code": 0},
        experiment_comparisons=[
            {
                "experiment_name": "hello",
                "basis": "bundled",
                "verdict": "different",
                "verify_script_path": "ree-scripts/experiments/hello.verify.sh",
                "expected_output_digest": "sha256:11",
                "observed_output_digest": "sha256:22",
                "expected_verify_exit_code": 0,
                "observed_verify_exit_code": 1,
            }
        ],
    )
    review(reviews, "review-new", newest, signed=True)
    return test


def test_the_final_review_is_the_newest_at_its_last_commit(tmp_path: Path) -> None:
    found = preserved_review(reviewed_test(tmp_path), ("missing", "author", "reviewer"))

    assert found is not None
    assert found.report.review_id == "review-new"
    assert found.report.status == "completed"
    assert found.signed
    assert found.report.experiment_comparisons[0].verdict == "different"


def test_a_test_that_left_no_review_has_no_final_review(tmp_path: Path) -> None:
    (tmp_path / "test/dossier/rees/author/ree").mkdir(parents=True)

    assert preserved_review(tmp_path / "test", ("author",)) is None


def test_the_page_shows_each_verdict_its_basis_and_its_evidence(tmp_path: Path) -> None:
    found = preserved_review(reviewed_test(tmp_path), ("author", "reviewer"))
    reviewing = ShowcaseTest(
        surface="api", workflow="review", file="r.py", tier="showcase-api", run="r", test="r.py::t"
    )
    showcase = Showcase(name="hello", kind="showcase", environment="bare", tests=(reviewing,))

    body = page_showcase_ree(showcase, None, None, reviewing, found).body

    assert '<section id="showcase-review-hello"><h2>Final review</h2>' in body
    assert '<code>review-new</code><br><span class="ok">completed</span> · <span class="ok">signed</span>' in body
    assert '<span class="ok">identical</span>' in body
    assert '<span class="ex">inconclusive</span>' in body
    assert '<span class="no">different</span>' in body
    assert f'<code>{SOURCE}</code> <span class="muted">expected and observed</span>' in body
    assert "0 matched, 0 missing, 1 extra, 0 versions differ" in body
    assert "<summary>Packages extra: 1</summary>" in body
    assert "<code>autocommand</code>" in body
    assert "<code>ree-scripts/experiments/hello.verify.sh</code> exited 1, the author's 0" in body
    assert '<span class="muted">expected</span> <code>sha256:11</code>' in body
    assert '<code>run_experiment</code> <span class="no">failed</span> verify exited 1' in body
    assert "no run of its API review test" in page_showcase_ree(showcase, None, None, None, None).body
    assert "preserved no review" in page_showcase_ree(showcase, None, None, reviewing, None).body


def test_a_real_world_showcase_reads_its_ree_and_its_review_from_its_one_test(tmp_path: Path) -> None:
    found = preserved_review(reviewed_test(tmp_path), ("author", "reviewer"))
    test = ShowcaseTest(surface="cli", workflow=None, file="w.py", tier="showcase-real-world", run="r", test="w.py::t")
    showcase = Showcase(name="world", kind="real_world", environment="docker", tests=(test,))

    assert authoring_test(showcase) == review_test(showcase) == test
    body = page_showcase_ree(showcase, review_test(showcase), None, review_test(showcase), found).body

    assert "The review the world showcase's test ran on a second machine from the sealed REE alone, as" in body
    assert "Its test preserved no sealed REE." in body
    assert '<code>review-new</code><br><span class="ok">completed</span>' in body
    assert "no run of its test." in page_showcase_ree(showcase, None, None, None, None).body

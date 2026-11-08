"""Several REEs at once, and a reviewer reproducing an REE someone else sealed."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from system_client import EXPERIMENT, Api


def test_two_rees_author_side_by_side(api: Api, new_ree: Callable[..., str]) -> None:
    rees = [new_ree(f"parallel-{index}") for index in range(2)]

    def author_and_seal(ree_id: str) -> str:
        api.author(ree_id)
        assert api.seal(ree_id)["status"] == "succeeded"
        return str(api.ree(ree_id)["seal"]["ree_digest"])

    with ThreadPoolExecutor(max_workers=len(rees)) as pool:
        digests = list(pool.map(author_and_seal, rees))
    assert len(set(digests)) == len(digests)


def test_reviewer_reproduces_a_sealed_ree(api: Api, new_ree: Callable[..., str]) -> None:
    author = new_ree("review-author")
    api.author(author)
    assert api.seal(author)["status"] == "succeeded"
    archive = api.keep_archive(author, "review-baseline")
    assert archive is not None
    data = archive.read_bytes()

    reviewer = new_ree("reviewer")
    upload = api.post(
        f"/api/v1/rees/{reviewer}/ree:upload-init",
        {"file_name": "ree.zip", "size": len(data), "content_type": "application/zip"},
    )
    api.request("PUT", upload["upload_url"], content=data)
    api.succeed(reviewer, "ree:load", {"upload_token": upload["upload_token"], "archive_name": "ree.zip"})

    source = api.stage(reviewer, "reviews/source:reproduce", {"basis": "auto"})
    assert source["status"] == "succeeded", api.logs(reviewer, source["run_id"])
    reviews = api.get(f"/api/v1/rees/{reviewer}/reviews")["reviews"]
    assert reviews, "a source review opens a review"
    review_id = reviews[0]["review_id"]

    for stage in ("build:reproduce", "activation:reproduce", f"experiments/{EXPERIMENT}:reproduce"):
        payload = {"basis": "auto"} if stage == "build:reproduce" else {}
        run = api.stage(reviewer, f"reviews/{review_id}/{stage}", payload)
        assert run["status"] == "succeeded", (stage, api.logs(reviewer, run["run_id"]))

    review = api.get(f"/api/v1/rees/{reviewer}/reviews/{review_id}")
    assert review, review

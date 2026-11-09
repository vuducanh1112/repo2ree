"""Sources fetched from an origin URL the stack serves itself, and fetched again by a reviewer."""

from __future__ import annotations

import os
import re

from typed_client import Client, NewRee

from repo2ree_testbed.api_models import AcquirableSourceType, SourceReceipt

SWHID = r"swh:1:dir:[0-9a-f]{40}"
GIT_ORIGIN = os.environ.get("E2E_GIT_ORIGIN_URL", "")
TARBALL_ORIGIN = os.environ.get("E2E_TARBALL_ORIGIN_URL", "")


def fetched(client: Client, ree_id: str, url: str, source_type: AcquirableSourceType) -> SourceReceipt:
    run = client.fetch_source(ree_id, url, source_type)
    assert run.status == "succeeded", client.logs(ree_id, run)
    receipt: SourceReceipt | None = client.ree(ree_id).subject.receipts.source
    assert receipt is not None
    assert receipt.origin_url == url
    assert receipt.source_type == source_type
    assert re.fullmatch(SWHID, receipt.observed_swhid or "")
    return receipt


def test_a_git_origin_is_fetched_and_its_commit_resolved(client: Client, new_ree: NewRee) -> None:
    receipt = fetched(client, new_ree(), GIT_ORIGIN, "git")

    assert re.fullmatch(r"[0-9a-f]{40}", receipt.resolved_revision or "")


def test_a_tarball_origin_is_fetched(client: Client, new_ree: NewRee) -> None:
    fetched(client, new_ree(), TARBALL_ORIGIN, "tarball")


def test_source_reproduction_refetches_the_pinned_origin_and_reports_identical(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree()
    fetched(client, ree_id, GIT_ORIGIN, "git")

    run = client.review_source(ree_id, "independent")
    assert run.status == "succeeded", client.logs(ree_id, run)

    [review] = client.reviews(ree_id)
    assert review.source_comparison is not None
    assert review.source_comparison.basis == "independent"
    assert review.source_comparison.verdict == "identical"

from __future__ import annotations

import zipfile

from typed_client import Client, NewRee
from upstream_release import author, publish

from repo2ree_testbed.showcases import RESULT, UNPINNED

F = UNPINNED


def test_the_build_takes_the_latest_upstream_release_and_the_authors_result_passes(
    client: Client, new_ree: NewRee
) -> None:
    publish(F, "1.0")
    ree_id = new_ree()
    author(client, ree_id, F)

    assert client.seal(ree_id, watch=F.watch).status == "succeeded"
    assert client.sign(ree_id).status == "succeeded"
    result = zipfile.ZipFile(client.archive(ree_id, "sealed")).read(f"ree/results/{F.experiment}/{RESULT}")
    assert result == b"mean: 296.25 K\n"

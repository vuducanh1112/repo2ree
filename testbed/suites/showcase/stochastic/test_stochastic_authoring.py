"""An experiment whose output changes on every run: the author seals one run's digits and the criterion for them."""

from __future__ import annotations

import re
import zipfile

from system_client import RESULT
from typed_client import Client, NewRee

from repo2ree_testbed.showcases import STOCHASTIC

F = STOCHASTIC


def test_an_estimate_within_the_authors_tolerance_is_sealed_and_downloaded(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree()
    client.author(ree_id, F)

    assert client.seal(ree_id).status == "succeeded"
    result = zipfile.ZipFile(client.archive(ree_id, "sealed")).read(f"ree/results/{F.experiment}/{RESULT}")
    assert re.search(rb"^pi estimate: \d\.\d{6}$", result, re.MULTILINE)

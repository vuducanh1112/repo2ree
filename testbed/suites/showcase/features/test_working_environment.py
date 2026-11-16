"""An REE's check of its working environment, on a machine that lacks what the check asks for."""

from __future__ import annotations

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import PYTHON_DOCKER

# The feature tests' machine has Python and no container engine; the Docker project's check asks for a daemon.
MISSING = "no Docker daemon is reachable"


def test_a_machine_missing_what_the_check_asks_for_fails_at_the_check_before_any_build(
    client: Client, new_ree: NewRee
) -> None:
    ree_id = new_ree()
    client.upload_source(ree_id, PYTHON_DOCKER)

    run = client.build_experiment_environment(ree_id, PYTHON_DOCKER)

    assert run.status == "failed"
    assert MISSING in client.logs(ree_id, run)
    receipts = client.ree(ree_id).subject.receipts
    assert receipts.working_environment_check is None
    assert receipts.experiment_environment is None

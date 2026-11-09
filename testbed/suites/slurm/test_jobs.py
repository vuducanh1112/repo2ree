"""An REE whose author's scripts submit their work to Slurm, which the product runs like any other script."""

from __future__ import annotations

import time
from collections.abc import Callable

from system_client import RESULT, Api, ApiError

from repo2ree_testbed.showcases import SLURM

HELD = "held"
SRUN_HELD = f"#!/usr/bin/env sh\nsrun --job-name={HELD} sh -c 'echo job-started; sleep 300'\n"
SBATCH_WAIT_HELD = f"#!/usr/bin/env sh\nsbatch --wait --job-name={HELD} --wrap 'sleep 300'\n"
NOTHING_TO_VERIFY = "#!/usr/bin/env sh\ntrue\n"
GONE_WITHIN_30S = f"""#!/usr/bin/env sh
: > {RESULT}
for _ in $(seq 30); do
  [ -z "$(squeue --noheader --name={HELD})" ] && exit 0
  sleep 1
done
exit 1
"""
STILL_QUEUED = f"""#!/usr/bin/env sh
: > {RESULT}
sleep 5
[ -n "$(squeue --noheader --name={HELD})" ]
"""


def built(api: Api, ree_id: str) -> None:
    api.acquire(ree_id, SLURM)
    api.succeed(ree_id, "evaluate")
    assert api.build(ree_id, fixture=SLURM)["status"] == "succeeded"


def holds(api: Api, ree_id: str, script: str) -> None:
    """``script``, run on the node as the experiment, exits 0."""
    run = api.experiment(ree_id, run=script, verify=NOTHING_TO_VERIFY, fixture=SLURM)
    assert run["status"] == "succeeded", api.logs(ree_id, run["run_id"])


def canceled_once_running(api: Api, ree_id: str, script: str, marker: str) -> None:
    """Start ``script`` as the experiment, cancel it once the job is up, and wait for the cancel to settle."""
    api.write(ree_id, SLURM.experiment_script, script)
    api.write(ree_id, SLURM.experiment_verify, NOTHING_TO_VERIFY)
    api.patch(ree_id, {"experiments": [{"name": SLURM.experiment, "output_paths": [RESULT]}]})
    run = api.post(f"/api/v1/rees/{ree_id}/experiments/{SLURM.experiment}:run")

    deadline = time.monotonic() + 60
    while marker not in api.logs(ree_id, run["run_id"]):
        if time.monotonic() > deadline:
            raise ApiError(f"the job never started\n{api.logs(ree_id, run['run_id'])}")
        time.sleep(0.5)

    api.post(f"/api/v1/rees/{ree_id}/runs/{run['run_id']}:cancel")
    assert api.wait(ree_id, run, timeout=60)["status"] == "canceled"


def test_a_job_that_fails_fails_the_experiment_and_leaves_no_receipt(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    built(api, ree_id)

    failed = api.experiment(ree_id, run="#!/usr/bin/env sh\nset -eu\nsrun sh -c 'exit 7'\n", fixture=SLURM)

    assert failed["status"] == "failed"
    assert SLURM.experiment not in api.ree(ree_id)["subject"]["receipts"]["experiments"]


def test_canceling_a_script_waiting_on_srun_ends_the_job(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    built(api, ree_id)

    canceled_once_running(api, ree_id, SRUN_HELD, "job-started")

    holds(api, ree_id, GONE_WITHIN_30S)


def test_canceling_a_script_waiting_on_sbatch_leaves_the_job_to_its_author(
    api: Api, new_ree: Callable[..., str]
) -> None:
    """The product stops the author's script and knows nothing of what it submitted."""
    ree_id = new_ree()
    built(api, ree_id)

    canceled_once_running(api, ree_id, SBATCH_WAIT_HELD, "Submitted batch job")

    holds(api, ree_id, STILL_QUEUED)

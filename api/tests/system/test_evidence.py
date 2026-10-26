"""Evidence follows what it was made from: it goes stale when that moves, and current again when made anew."""

from __future__ import annotations

from collections.abc import Callable

from system_client import ACTIVATION_SCRIPT, EXPERIMENT, EXPERIMENT_SCRIPT, EXPERIMENT_VERIFY, Api, recipe

ACTIVATION_VERIFY = "ree-scripts/activation.verify.sh"
PASSING_VERIFY = "#!/usr/bin/env sh\nset -eu\nexit 0\n"


def standing(api: Api, ree_id: str) -> dict[str, str]:
    audit = api.audit(ree_id)
    steps = ("source", "evaluation", "hardware", "runtime", "test_activation")
    found = {step: str(audit[step]["evidence"]) for step in steps}
    return found | {f"experiment:{item['name']}": str(item["run"]["evidence"]) for item in audit["experiments"]}


def test_rewriting_or_deleting_a_script_makes_what_it_ran_stale(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)
    api.write(ree_id, ACTIVATION_VERIFY, PASSING_VERIFY)
    api.succeed(ree_id, "activation-test")

    api.write(ree_id, ACTIVATION_SCRIPT, recipe("activation.sh") + "# touched\n")
    api.write(ree_id, EXPERIMENT_SCRIPT, recipe("experiment.sh") + "# touched\n")
    edited = standing(api, ree_id)
    assert (edited["test_activation"], edited[f"experiment:{EXPERIMENT}"]) == ("stale", "stale")

    api.succeed(ree_id, "activation-test")
    api.succeed(ree_id, f"experiments/{EXPERIMENT}:run")
    for path in (ACTIVATION_VERIFY, EXPERIMENT_VERIFY):
        api.request("DELETE", f"/api/v1/rees/{ree_id}/files/content", params={"path": path})
    deleted = standing(api, ree_id)
    assert (deleted["test_activation"], deleted[f"experiment:{EXPERIMENT}"]) == ("stale", "stale")


def test_removing_the_source_clears_the_evidence_made_from_it(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)

    api.request("DELETE", f"/api/v1/rees/{ree_id}/source")
    removed = standing(api, ree_id)
    assert (removed["source"], removed["evaluation"]) == ("not_applicable", "not_applicable")
    # What is still declared waits to run again; the hardware observation stands on its own.
    assert (removed["runtime"], removed["test_activation"], removed["hardware"]) == ("missing", "missing", "current")
    assert api.ree(ree_id)["subject"]["definition"]["source"] is None

    api.acquire(ree_id)
    api.succeed(ree_id, "evaluate")
    api.succeed(ree_id, "build-runtime")
    reacquired = standing(api, ree_id)
    assert (reacquired["source"], reacquired["evaluation"], reacquired["runtime"]) == ("current", "current", "current")

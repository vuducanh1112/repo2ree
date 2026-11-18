"""Evidence follows what it was made from: it goes stale when that moves, and current again when made anew."""

from __future__ import annotations

from collections.abc import Callable

from system_client import (
    ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    EXPERIMENT,
    EXPERIMENT_SCRIPT,
    EXPERIMENT_VERIFY,
    Api,
    recipe,
)


def standing(api: Api, ree_id: str) -> dict[str, str]:
    audit = api.audit(ree_id)
    steps = (
        "acquire_source",
        "evaluate_reproducibility",
        "observe_hardware",
        "build_experiment_environment",
        "activate_experiment_environment",
    )
    found = {step: str(audit[step]["evidence"]) for step in steps}
    return found | {f"run_experiment:{item['name']}": str(item["run"]["evidence"]) for item in audit["experiments"]}


def test_rewriting_or_deleting_a_script_makes_what_it_ran_stale(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)

    # Every experiment runs inside the activation: rewriting it stales the activation and them.
    api.write(
        ree_id, ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, recipe("activate_experiment_environment.sh") + "# touched\n"
    )
    edited = standing(api, ree_id)
    assert (edited["activate_experiment_environment"], edited[f"run_experiment:{EXPERIMENT}"]) == ("stale", "stale")
    api.succeed(ree_id, "activate-experiment-environment")
    assert standing(api, ree_id)[f"run_experiment:{EXPERIMENT}"] == "stale"
    api.succeed(ree_id, f"run-experiment/{EXPERIMENT}")
    assert standing(api, ree_id)[f"run_experiment:{EXPERIMENT}"] == "current"

    api.write(ree_id, EXPERIMENT_SCRIPT, recipe("experiment.sh") + "# touched\n")
    assert standing(api, ree_id)[f"run_experiment:{EXPERIMENT}"] == "stale"
    api.succeed(ree_id, f"run-experiment/{EXPERIMENT}")
    api.write(ree_id, EXPERIMENT_VERIFY, "#!/usr/bin/env sh\nset -eu\nexit 0\n")
    unchecked = standing(api, ree_id)
    assert (unchecked["activate_experiment_environment"], unchecked[f"run_experiment:{EXPERIMENT}"]) == (
        "current",
        "stale",
    )


def test_removing_the_source_clears_the_evidence_made_from_it(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)

    api.request("POST", f"/api/v1/rees/{ree_id}/remove-source")
    removed = standing(api, ree_id)
    assert (removed["acquire_source"], removed["evaluate_reproducibility"]) == ("not_applicable", "not_applicable")
    # What is still declared waits to run again; the hardware observation stands on its own.
    assert (
        removed["build_experiment_environment"],
        removed["activate_experiment_environment"],
        removed["observe_hardware"],
    ) == (
        "missing",
        "missing",
        "current",
    )
    assert api.ree(ree_id)["subject"]["definition"]["source"] is None

    api.acquire(ree_id)
    api.succeed(ree_id, "evaluate-reproducibility")
    api.succeed(ree_id, "build-experiment-environment")
    reacquired = standing(api, ree_id)
    assert (
        reacquired["acquire_source"],
        reacquired["evaluate_reproducibility"],
        reacquired["build_experiment_environment"],
    ) == (
        "current",
        "current",
        "current",
    )

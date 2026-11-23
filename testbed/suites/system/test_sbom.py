from __future__ import annotations

from collections.abc import Callable

from system_client import BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, EXPERIMENT_ENVIRONMENT, Api


def standing(api: Api, ree_id: str) -> tuple[str, str, str]:
    audit = api.audit(ree_id)
    experiment_environment, sbom, cross_check = (
        str(audit[step]["evidence"]) for step in ("build_experiment_environment", "generate_sbom", "cross_check_sbom")
    )
    return experiment_environment, sbom, cross_check


def test_each_receipt_follows_only_what_it_was_made_from(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)
    assert standing(api, ree_id) == ("current", "missing", "missing")

    api.succeed(ree_id, "generate-sbom")
    api.succeed(ree_id, "cross-check-sbom")
    assert standing(api, ree_id) == ("current", "current", "current")

    build_experiment_environment_script = str(
        api.infer(ree_id, "build_experiment_environment")["candidates"][0]["body"]
    )
    api.write(ree_id, BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, build_experiment_environment_script + "# touched\n")
    assert standing(api, ree_id) == ("stale", "current", "current")
    api.succeed(ree_id, "build-experiment-environment")
    assert standing(api, ree_id) == ("current", "stale", "current")
    api.succeed(ree_id, "generate-sbom")
    assert standing(api, ree_id) == ("current", "current", "stale")
    api.succeed(ree_id, "cross-check-sbom")
    assert standing(api, ree_id) == ("current", "current", "current")

    api.patch(ree_id, {"experiment_environment": None}, expect=400)
    assert standing(api, ree_id) == ("current", "current", "current")
    api.patch(ree_id, {"experiment_environment": {"artifact_path": None}})
    assert standing(api, ree_id) == ("stale", "stale", "stale")


def test_removing_the_source_clears_the_sbom_and_its_cross_check(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)
    api.succeed(ree_id, "generate-sbom")
    api.succeed(ree_id, "cross-check-sbom")

    api.request("POST", f"/api/v1/rees/{ree_id}/remove-source")
    _, sbom, cross_check = standing(api, ree_id)
    assert cross_check == "not_applicable"
    assert sbom in {"missing", "not_applicable"}

    api.acquire(ree_id)
    assert standing(api, ree_id)[2] == "missing"
    api.succeed(ree_id, "evaluate-reproducibility")
    api.patch(ree_id, {"experiment_environment": {"artifact_path": EXPERIMENT_ENVIRONMENT}})
    api.succeed(ree_id, "build-experiment-environment")
    api.succeed(ree_id, "generate-sbom")
    api.succeed(ree_id, "cross-check-sbom")
    assert standing(api, ree_id) == ("current", "current", "current")

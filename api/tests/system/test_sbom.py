"""The SBOM is observed in whatever tarball the build packed, and follows what it was made from."""

from __future__ import annotations

from collections.abc import Callable

from system_client import BUILD_SCRIPT, PROJECT_DIR, RUNTIME, Api


def standing(api: Api, ree_id: str) -> tuple[str, str, str]:
    """The runtime, its SBOM, and the cross-check of that SBOM against the evaluation."""
    audit = api.audit(ree_id)
    runtime, sbom, cross_check = (str(audit[step]["evidence"]) for step in ("runtime", "sbom", "sbom_cross_check"))
    return runtime, sbom, cross_check


def test_each_receipt_follows_only_what_it_was_made_from(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)
    assert standing(api, ree_id) == ("current", "missing", "missing")

    # The instant project's runtime is a packed venv, not an image.
    api.succeed(ree_id, "generate-sbom")
    api.succeed(ree_id, "cross-check-sbom")
    assert standing(api, ree_id) == ("current", "current", "current")

    # A changed build script outdates the runtime; the SBOM still describes the tarball that exists.
    build_script = str(api.infer(ree_id, "build")["candidates"][0]["body"])
    api.write(ree_id, BUILD_SCRIPT, build_script + "# touched\n")
    assert standing(api, ree_id) == ("stale", "current", "current")
    # A new tarball outdates the SBOM; the cross-check still describes the SBOM that exists.
    api.succeed(ree_id, "build-runtime")
    assert standing(api, ree_id) == ("current", "stale", "current")
    api.succeed(ree_id, "generate-sbom")
    assert standing(api, ree_id) == ("current", "current", "stale")
    api.succeed(ree_id, "cross-check-sbom")
    assert standing(api, ree_id) == ("current", "current", "current")

    # A manifest the author adds changes what the evaluation declares, and so the cross-check against it.
    api.write(ree_id, f"{PROJECT_DIR}/requirements-extra.txt", "requests==2.31.0\n")
    api.succeed(ree_id, "evaluate")
    assert standing(api, ree_id) == ("current", "current", "stale")
    api.succeed(ree_id, "cross-check-sbom")

    # The build is undeclared through the definition, never by deleting its script.
    api.request("DELETE", f"/api/v1/rees/{ree_id}/files/content", params={"path": BUILD_SCRIPT}, expect=400)
    assert standing(api, ree_id) == ("current", "current", "current")
    # Undeclaring the runtime orphans all three.
    api.patch(ree_id, {"build_runtime": {"runtime_path": None}})
    assert standing(api, ree_id) == ("stale", "stale", "stale")


def test_removing_the_source_clears_the_sbom_and_its_cross_check(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)
    api.succeed(ree_id, "generate-sbom")
    api.succeed(ree_id, "cross-check-sbom")

    api.request("DELETE", f"/api/v1/rees/{ree_id}/source")
    _, sbom, cross_check = standing(api, ree_id)
    assert cross_check == "not_applicable"
    assert sbom in {"missing", "not_applicable"}

    api.acquire(ree_id)
    assert standing(api, ree_id)[2] == "missing"
    api.succeed(ree_id, "evaluate")
    api.patch(ree_id, {"build_runtime": {"runtime_path": RUNTIME}})
    api.succeed(ree_id, "build-runtime")
    api.succeed(ree_id, "generate-sbom")
    api.succeed(ree_id, "cross-check-sbom")
    assert standing(api, ree_id) == ("current", "current", "current")

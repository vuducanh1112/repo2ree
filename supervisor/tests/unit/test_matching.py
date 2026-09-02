"""The compatibility gate: one selected profile against one observation.

The gate answers accept/reject and nothing else. It never searches for a
better-fitting profile, never relaxes a requirement, and never touches the
workbench it is judging.
"""

from __future__ import annotations

from repo2ree_protocol import (
    FixedResources,
    ObservedCapabilities,
    RequiredCapabilities,
    StoragePolicy,
    SubstrateKind,
    WorkbenchProfile,
)
from repo2ree_supervisor.matching import check_compatibility, describe_issues


def _profile(**required: object) -> WorkbenchProfile:
    fields: dict[str, object] = {
        "substrate": SubstrateKind.DOCKER_NESTED,
        "resources": FixedResources(),
    }
    fields.update(required)
    return WorkbenchProfile(
        id="standard",
        revision="1",
        location_id="lab-1",
        label="Standard",
        required=RequiredCapabilities(**fields),  # type: ignore[arg-type]
        storage_policy=StoragePolicy.EPHEMERAL,
    )


def _observation(**overrides: object) -> ObservedCapabilities:
    fields: dict[str, object] = {
        "root_writable": True,
        "executor_available": True,
        "substrate": SubstrateKind.DOCKER_NESTED,
        "docker_version": "29.0.1",
        "resources": FixedResources(),
    }
    fields.update(overrides)
    return ObservedCapabilities(**fields)  # type: ignore[arg-type]


def _codes(profile: WorkbenchProfile, observation: ObservedCapabilities) -> set[str]:
    return {issue.code for issue in check_compatibility(profile, observation)}


def test_a_workbench_meeting_the_profile_raises_no_issue() -> None:
    assert check_compatibility(_profile(), _observation()) == ()


def test_an_unusable_workbench_is_rejected_on_every_count_at_once() -> None:
    # Every failure is reported together: an author fixing a deployment should
    # see the whole gap, not discover it one provisioning attempt at a time.
    issues = _codes(
        _profile(),
        _observation(root_writable=False, executor_available=False, substrate=SubstrateKind.BARE),
    )
    assert issues == {"root_not_writable", "executor_unavailable", "substrate_mismatch"}


def test_substrate_is_compared_exactly_rather_than_ranked() -> None:
    # A host-socket bench is not a substitute for a nested one, even though it
    # also has Docker: the gate compares, it does not rank.
    profile = _profile(substrate=SubstrateKind.DOCKER_NESTED)
    issue = next(iter(check_compatibility(profile, _observation(substrate=SubstrateKind.DOCKER_HOST_SOCKET))))
    assert issue.code == "substrate_mismatch"
    assert (issue.expected, issue.observed) == ("docker-nested", "docker-host-socket")


def test_docker_version_floor_accepts_newer_and_rejects_older() -> None:
    profile = _profile(minimum_docker_version="29.0.0")
    assert check_compatibility(profile, _observation(docker_version="29.1.0")) == ()
    assert _codes(profile, _observation(docker_version="28.9.9")) == {"docker_version_too_old"}
    assert _codes(profile, _observation(substrate=SubstrateKind.BARE, docker_version=None)) == {
        "substrate_mismatch",
        "docker_unavailable",
    }


def test_fixed_resource_floors_reject_only_a_measured_shortfall() -> None:
    profile = _profile(resources=FixedResources(cpu_count=4, memory_bytes=8 * 1024**3))
    assert (
        check_compatibility(profile, _observation(resources=FixedResources(cpu_count=8, memory_bytes=16 * 1024**3)))
        == ()
    )
    assert _codes(profile, _observation(resources=FixedResources(cpu_count=2, memory_bytes=4 * 1024**3))) == {
        "cpu_shortfall",
        "memory_shortfall",
    }
    # A bench that reports no limit is not treated as a bench that reports zero.
    assert check_compatibility(profile, _observation(resources=FixedResources())) == ()


def test_a_rejection_names_what_was_expected_and_what_was_found() -> None:
    # A bare "does not match" leaves an operator unable to tell which side is
    # wrong; the pair is what makes a provisioning log actionable.
    issues = check_compatibility(_profile(), _observation(substrate=SubstrateKind.DOCKER_HOST_SOCKET))

    assert describe_issues(issues) == (
        "The workbench substrate does not match the selected profile. "
        "(expected docker-nested, observed docker-host-socket)"
    )


def test_an_issue_with_no_comparison_renders_as_its_detail_alone() -> None:
    issues = check_compatibility(_profile(), _observation(root_writable=False))

    assert describe_issues(issues) == "The workbench root is not writable."

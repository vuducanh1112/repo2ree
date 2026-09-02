"""A compatibility gate for one selected profile and one workbench.

This module intentionally has no placement/search API.  A mismatch is reported
to the caller; it never selects another profile or mutates the environment.
"""

from __future__ import annotations

import re

from repo2ree_protocol.allocation import WorkbenchProfile
from repo2ree_protocol.substrate import CompatibilityIssue, ObservedCapabilities


def check_compatibility(profile: WorkbenchProfile, observation: ObservedCapabilities) -> tuple[CompatibilityIssue, ...]:
    issues: list[CompatibilityIssue] = []
    required = profile.required
    if not observation.root_writable:
        issues.append(CompatibilityIssue(code="root_not_writable", detail="The workbench root is not writable."))
    if not observation.executor_available:
        issues.append(CompatibilityIssue(code="executor_unavailable", detail="The REE executor is unavailable."))
    if observation.substrate != required.substrate:
        issues.append(
            CompatibilityIssue(
                code="substrate_mismatch",
                detail="The workbench substrate does not match the selected profile.",
                expected=required.substrate,
                observed=observation.substrate,
            )
        )
    if required.minimum_docker_version:
        if not observation.docker_version:
            issues.append(CompatibilityIssue(code="docker_unavailable", detail="The selected profile requires Docker."))
        elif not _version_at_least(observation.docker_version, required.minimum_docker_version):
            issues.append(
                CompatibilityIssue(
                    code="docker_version_too_old",
                    detail="The observed Docker version is below the profile minimum.",
                    expected=required.minimum_docker_version,
                    observed=observation.docker_version,
                )
            )
    observed_resources = observation.resources
    required_resources = required.resources
    if (
        required_resources.cpu_count is not None
        and observed_resources.cpu_count is not None
        and observed_resources.cpu_count < required_resources.cpu_count
    ):
        issues.append(
            CompatibilityIssue(
                code="cpu_shortfall",
                detail="The workbench CPU limit is below the fixed profile requirement.",
                expected=str(required_resources.cpu_count),
                observed=str(observed_resources.cpu_count),
            )
        )
    if (
        required_resources.memory_bytes is not None
        and observed_resources.memory_bytes is not None
        and observed_resources.memory_bytes < required_resources.memory_bytes
    ):
        issues.append(
            CompatibilityIssue(
                code="memory_shortfall",
                detail="The workbench memory limit is below the fixed profile requirement.",
                expected=str(required_resources.memory_bytes),
                observed=str(observed_resources.memory_bytes),
            )
        )
    return tuple(issues)


def _version_at_least(observed: str, required: str) -> bool:
    def parts(value: str) -> tuple[int, ...]:
        return tuple(int(part) for part in re.findall(r"\d+", value))

    observed_parts = parts(observed)
    required_parts = parts(required)
    return bool(observed_parts and required_parts and observed_parts >= required_parts)


def describe_issues(issues: tuple[CompatibilityIssue, ...]) -> str:
    """Render issues for a human reading a provisioning log.

    The expected/observed pair is the whole diagnostic value of a rejection —
    without it "the substrate does not match" leaves an operator unable to tell
    which side is wrong, or which way.
    """
    return "; ".join(
        issue.detail + (f" (expected {issue.expected}, observed {issue.observed})" if issue.expected else "")
        for issue in issues
    )

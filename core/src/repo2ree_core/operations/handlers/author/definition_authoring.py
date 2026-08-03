"""Hydrate authored definition identities from authoritative overlay bytes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.model import ReeDefinition
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)


def patched_definition(current: ReeDefinition, patch: dict[str, Any], layout: ReeLayout) -> ReeDefinition:
    unknown = sorted(set(patch) - set(ReeDefinition.model_fields))
    if unknown:
        raise ValueError(f"definition patch contains unknown fields: {unknown}")
    payload = current.model_dump(mode="json")
    payload.update(patch)
    return hydrate_definition_payload(payload, layout)


def rehydrate_after_file_mutation(
    definition: ReeDefinition,
    changed_path: str,
    layout: ReeLayout,
) -> ReeDefinition:
    payload = definition.model_dump(mode="json")
    if changed_path == RESERVED_BUILD_SCRIPT and not layout.overlay_file(changed_path).is_file():
        payload["build_runtime"] = None
    if changed_path == RESERVED_ACTIVATION_SCRIPT and not layout.overlay_file(changed_path).is_file():
        payload["test_activation"] = None
    experiments = []
    for experiment in payload.get("experiments") or []:
        run_path = experiment_run_script_path(str(experiment["name"]))
        if changed_path == run_path and not layout.overlay_file(run_path).is_file():
            continue
        experiments.append(experiment)
    payload["experiments"] = experiments
    return hydrate_definition_payload(payload, layout)


def hydrate_definition_payload(payload: dict[str, Any], layout: ReeLayout) -> ReeDefinition:
    hydrated = dict(payload)
    build = hydrated.get("build_runtime")
    if build is not None:
        script = _required_overlay_file(layout, RESERVED_BUILD_SCRIPT, "runtime build script")
        hydrated["build_runtime"] = {
            "build_runtime_script_path": RESERVED_BUILD_SCRIPT,
            "build_runtime_script_digest": digest_file(script),
            "build_runtime_script_size": script.stat().st_size,
        }

    activation = hydrated.get("test_activation")
    if activation is not None:
        run_script = _required_overlay_file(layout, RESERVED_ACTIVATION_SCRIPT, "activation script")
        verify_script = layout.overlay_file(RESERVED_ACTIVATION_VERIFY_SCRIPT)
        hydrated["test_activation"] = {
            "run_script_path": RESERVED_ACTIVATION_SCRIPT,
            "run_script_digest": digest_file(run_script),
            "run_script_size": run_script.stat().st_size,
            "verify_script_path": RESERVED_ACTIVATION_VERIFY_SCRIPT if verify_script.is_file() else None,
            "verify_script_digest": digest_file(verify_script) if verify_script.is_file() else None,
            "verify_script_size": verify_script.stat().st_size if verify_script.is_file() else None,
        }

    experiments: list[dict[str, Any]] = []
    for raw in hydrated.get("experiments") or []:
        experiment = dict(raw)
        name = str(experiment.get("name") or "")
        run_path = experiment_run_script_path(name)
        verify_path = experiment_verify_script_path(name)
        run_script = _required_overlay_file(layout, run_path, f"experiment {name!r} run script")
        verify_script = layout.overlay_file(verify_path)
        experiments.append(
            {
                "name": name,
                "run_script_path": run_path,
                "run_script_digest": digest_file(run_script),
                "run_script_size": run_script.stat().st_size,
                "verify_script_path": verify_path if verify_script.is_file() else None,
                "verify_script_digest": digest_file(verify_script) if verify_script.is_file() else None,
                "verify_script_size": verify_script.stat().st_size if verify_script.is_file() else None,
                "output_paths": experiment.get("output_paths") or [],
            }
        )
    hydrated["experiments"] = experiments
    return ReeDefinition.model_validate(hydrated)


def _required_overlay_file(layout: ReeLayout, path: str, label: str) -> Path:
    absolute = layout.overlay_file(path)
    if not absolute.is_file():
        raise ValueError(f"{label} is not authored at {path}")
    return absolute

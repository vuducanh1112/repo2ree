"""Hydrate authored definition identities from authoritative overlay bytes, and keep each declaration's scripts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo2ree_authoring.templates import experiment_run_templates, verify_templates
from repo2ree_core.digests import digest_file
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_ree.model import ReeDefinition, SourceDefinition
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT,
    RESERVED_LAUNCH_SCRIPT,
    RESERVED_OVERLAY_SCRIPTS,
    experiment_run_script_path,
    experiment_verify_script_path,
)

FIXED_DECLARATIONS = {
    "experiment_environment": "build experiment environment script",
    "activate_experiment_environment": "activate experiment environment script",
    "launch": "launch script",
    "check_working_environment": "check script",
}


@dataclass(frozen=True)
class ExperimentScripts:
    """The scripts a definition patch brings into being for the experiments it declares, and those it takes away.

    An experiment that names the run script of one the patch removes is that one renamed: it takes its scripts along.
    """

    moved: dict[str, str]
    seeded: dict[str, str]
    removed: tuple[str, ...]


def experiment_script_paths(name: str) -> tuple[str, str]:
    return experiment_run_script_path(name), experiment_verify_script_path(name)


def experiment_scripts(current: ReeDefinition, patch: dict[str, Any], layout: ReeLayout) -> ExperimentScripts:
    """Each declared experiment has its run and verify scripts, starting as their defaults; a removed one has none."""
    if "experiments" not in patch:
        return ExperimentScripts({}, {}, ())
    entries = [dict(raw) for raw in patch["experiments"] or []]
    names = [str(entry.get("name") or "") for entry in entries]
    declared = {path for name in names for path in experiment_script_paths(name)}
    gone = {
        experiment_run_script_path(experiment.name): experiment.name
        for experiment in current.experiments
        if experiment.name not in names
    }
    renames = [
        (renamed, name)
        for entry, name in zip(entries, names, strict=True)
        if (renamed := gone.pop(str(entry.get("run_script_path") or ""), None)) is not None
    ]
    moved = {
        source: target
        for renamed, name in renames
        for source, target in zip(experiment_script_paths(renamed), experiment_script_paths(name), strict=True)
        if source != target and layout.overlay_file(source).is_file() and not layout.overlay_file(target).is_file()
    }
    run_default = experiment_run_templates()[0].body
    verify_default = verify_templates()[0].body
    seeded = {
        path: verify_default if path.endswith(".verify.sh") else run_default
        for path in sorted(declared - set(moved.values()))
        if not layout.overlay_file(path).is_file()
    }
    removed = tuple(
        sorted(
            path
            for experiment in current.experiments
            for path in experiment_script_paths(experiment.name)
            if path not in declared and path not in moved and layout.overlay_file(path).is_file()
        )
    )
    return ExperimentScripts(moved, seeded, removed)


def is_script_of(definition: ReeDefinition, path: str) -> bool:
    """Whether the REE has the script at ``path``: a fixed one, or one of a declared experiment's."""
    return path in RESERVED_OVERLAY_SCRIPTS or any(
        path in experiment_script_paths(experiment.name) for experiment in definition.experiments
    )


def patched_definition(current: ReeDefinition, patch: dict[str, Any], layout: ReeLayout) -> ReeDefinition:
    unknown = sorted(set(patch) - set(ReeDefinition.model_fields))
    if unknown:
        raise ValueError(f"definition patch contains unknown fields: {unknown}")
    # The source changes only by acquiring or removing it; a whole definition may repeat it unchanged.
    if "source" in patch and _source(patch["source"]) != current.source:
        raise ValueError("the source changes only by acquiring or removing it, not by a definition patch")
    for field, label in FIXED_DECLARATIONS.items():
        if field in patch and patch[field] is None and getattr(current, field) is not None:
            raise ValueError(f"every REE has its {label}: write the script rather than undeclaring it")
    payload = current.model_dump(mode="json")
    payload.update(patch)
    definition = hydrate_definition_payload(payload, layout)
    # An REE is created with a name (its id's prefix if none is given); an edit renames it, never unnames it.
    if not definition.name.strip():
        raise ValueError("an REE's name cannot be empty")
    return definition


def _source(value: Any) -> SourceDefinition | None:
    return None if value is None else SourceDefinition.model_validate(value)


def rehydrate_after_file_mutation(definition: ReeDefinition, layout: ReeLayout) -> ReeDefinition:
    return hydrate_definition_payload(definition.model_dump(mode="json"), layout)


def hydrate_definition_payload(payload: dict[str, Any], layout: ReeLayout) -> ReeDefinition:
    hydrated = dict(payload)
    build = hydrated.get("experiment_environment")
    if build is not None:
        recipe = build if isinstance(build, dict) else {}
        script = _required_overlay_file(
            layout, RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, "build experiment environment script"
        )
        hydrated["experiment_environment"] = {
            "build_experiment_environment_script_path": RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
            "build_experiment_environment_script_digest": digest_file(script),
            "build_experiment_environment_script_size": script.stat().st_size,
            # Carried through rather than derived. A script's identity is read
            # off the authored file and never taken from the client, but where
            # the build leaves its experiment environment is the author's own declaration —
            # the same split the experiment branch makes for ``output_paths``.
            "artifact_path": recipe.get("artifact_path"),
        }

    if hydrated.get("activate_experiment_environment") is not None:
        activate = _required_overlay_file(
            layout, RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, "activate experiment environment script"
        )
        hydrated["activate_experiment_environment"] = {
            "activate_experiment_environment_script_path": RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
            "activate_experiment_environment_script_digest": digest_file(activate),
            "activate_experiment_environment_script_size": activate.stat().st_size,
        }

    if hydrated.get("launch") is not None:
        launch = _required_overlay_file(layout, RESERVED_LAUNCH_SCRIPT, "launch script")
        hydrated["launch"] = {
            "launch_script_path": RESERVED_LAUNCH_SCRIPT,
            "launch_script_digest": digest_file(launch),
            "launch_script_size": launch.stat().st_size,
        }

    if hydrated.get("check_working_environment") is not None:
        check = _required_overlay_file(layout, RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT, "check script")
        hydrated["check_working_environment"] = {
            "check_working_environment_script_path": RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT,
            "check_working_environment_script_digest": digest_file(check),
            "check_working_environment_script_size": check.stat().st_size,
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

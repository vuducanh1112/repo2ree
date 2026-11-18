"""Hydrate authored definition identities from authoritative overlay bytes, and keep each declaration's scripts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo2ree_authoring.templates import experiment_run_templates, experiment_verify_templates
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

FIXED_SCRIPTS = {
    "experiment_environment": ("build_experiment_environment", RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
    "activate_experiment_environment": (
        "activate_experiment_environment",
        RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    ),
    "launch": ("launch", RESERVED_LAUNCH_SCRIPT),
    "check_working_environment": ("check_working_environment", RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT),
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
    defaults = (experiment_run_templates()[0].body, experiment_verify_templates()[0].body)
    seeded = {
        path: default
        for name in names
        for path, default in zip(experiment_script_paths(name), defaults, strict=True)
        if path not in moved.values() and not layout.overlay_file(path).is_file()
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
    if undeclared := sorted(field for field in FIXED_SCRIPTS if field in patch and patch[field] is None):
        raise ValueError(f"every REE declares {', '.join(undeclared)}: write the script rather than undeclaring it")
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
    """The definition with each script's identity read off its authored bytes, never taken from the payload."""
    hydrated = dict(payload)
    for field, (prefix, path) in FIXED_SCRIPTS.items():
        script = _required_overlay_file(layout, path, f"{prefix.replace('_', ' ')} script")
        hydrated[field] = {
            f"{prefix}_script_path": path,
            f"{prefix}_script_digest": digest_file(script),
            f"{prefix}_script_size": script.stat().st_size,
        }
    # Where the build leaves the experiment environment is the author's own declaration, carried through.
    build = payload.get("experiment_environment")
    hydrated["experiment_environment"]["artifact_path"] = (
        build.get("artifact_path") if isinstance(build, dict) else None
    )

    experiments: list[dict[str, Any]] = []
    for raw in hydrated.get("experiments") or []:
        experiment = dict(raw)
        name = str(experiment.get("name") or "")
        run_path, verify_path = experiment_script_paths(name)
        run_script = _required_overlay_file(layout, run_path, f"experiment {name!r} run script")
        verify_script = _required_overlay_file(layout, verify_path, f"experiment {name!r} verify script")
        experiments.append(
            {
                "name": name,
                "run_script_path": run_path,
                "run_script_digest": digest_file(run_script),
                "run_script_size": run_script.stat().st_size,
                "verify_script_path": verify_path,
                "verify_script_digest": digest_file(verify_script),
                "verify_script_size": verify_script.stat().st_size,
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

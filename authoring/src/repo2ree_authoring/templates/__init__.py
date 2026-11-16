"""Starter templates for the reserved, REE-owned overlay scripts.

Each template is a dedicated ``.sh`` file shipped inside this package — the
single source of truth for the starter content authors (human or workbench) work
from. The build, activate and check templates are seeded into the overlay at REE
creation (``ReeDirectory.ensure_reserved_overlay_scripts``); the launch template is not, since an REE without a
launch script runs its scripts directly; the per-experiment run
and verify templates cannot be seeded (their paths only exist once an
experiment is named), so ``ree templates`` prints them for clients to prefill from.

Every script kind carries a catalog of named :class:`ScriptTemplate` variants,
one per standard case, so new strategies (a nix build, …) slot in as further
entries. The first variant is the default, and for the seeded scripts it is the
content a fresh REE starts with: one that needs no container engine.

Leaf module like ``reserved_paths``: it imports nothing from
``repo2ree_core``, so any layer can load templates without an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files

from repo2ree_protocol.catalog import (
    ActivateExperimentEnvironmentScriptTemplates,
    BuildExperimentEnvironmentScriptTemplates,
    CheckWorkingEnvironmentScriptTemplates,
    ExperimentScriptTemplates,
    LaunchScriptTemplates,
    ScriptTemplateCatalog,
    ScriptTemplateEntry,
)
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT,
    RESERVED_EXPERIMENT_SCRIPT_DIR,
    RESERVED_LAUNCH_SCRIPT,
)


def _template(name: str) -> str:
    return files(__package__).joinpath(name).read_text(encoding="utf-8")


@dataclass(frozen=True)
class ScriptTemplate:
    """A named starter-template variant for one of the REE-owned scripts.

    Bodies are ready to run rather than commented-out sketches, with the
    project-specific knobs (image tag, Dockerfile, run-log path, …) as plainly
    assigned variables the author edits in place. Verify bodies additionally
    carry EDIT-ME placeholders for the claim being checked.
    """

    key: str
    label: str
    description: str
    body: str


def reserved_script_template(reserved_path: str) -> str:
    """Return the default starter template for a seeded reserved script path: the first of its catalog.

    Catalogs are keyed by the script's file name, so the lookup is stable
    under renames of the reserved directory itself.
    """
    catalogs = {
        "build_experiment_environment.sh": build_templates,
        "activate_experiment_environment.sh": activate_experiment_environment_templates,
        "check_working_environment.sh": check_working_environment_templates,
    }
    templates = catalogs[reserved_path.rsplit("/", 1)[-1]]()
    return templates[0].body


def build_templates() -> tuple[ScriptTemplate, ...]:
    """The build-script templates, one per runtime-packaging strategy."""
    return (
        ScriptTemplate(
            key="venv",
            label="Python virtual environment",
            description=(
                "Install requirements.txt into a virtual environment on the host "
                "and pack it as the experiment environment."
            ),
            body=_template("build_experiment_environment_venv.sh"),
        ),
        ScriptTemplate(
            key="docker",
            label="Docker image",
            description=(
                "Build the project's Dockerfile into an image and save it as the experiment environment tarball."
            ),
            body=_template("build_experiment_environment_docker.sh"),
        ),
    )


def activate_experiment_environment_templates() -> tuple[ScriptTemplate, ...]:
    """The activate experiment environment templates, one per experiment environment strategy."""
    return (
        ScriptTemplate(
            key="venv",
            label="Python virtual environment",
            description="Restore the packed virtual environment and run the given command with it on the path.",
            body=_template("activate_experiment_environment_venv.sh"),
        ),
        ScriptTemplate(
            key="docker",
            label="Docker experiment environment",
            description="Load the saved image and run the given command in a container from it, "
            "with the workspace mounted at its own path.",
            body=_template("activate_experiment_environment_docker.sh"),
        ),
    )


def launch_templates() -> tuple[ScriptTemplate, ...]:
    """The launch-script templates, one per launcher. An REE with no launch script runs its scripts directly."""
    return (
        ScriptTemplate(
            key="slurm",
            label="Slurm job step",
            description="Run each of the REE's scripts as a Slurm job step with the resources it needs, "
            "taking a reproducer's own options last.",
            body=_template("launch_slurm.sh"),
        ),
    )


def check_working_environment_templates() -> tuple[ScriptTemplate, ...]:
    """The check-script templates; the first is the check every REE starts with, which passes as it comes."""
    return (
        ScriptTemplate(
            key="standard-tools",
            label="Standard tools",
            description="Commented checks for common needs (Python, compilers, Java, a container engine, NVIDIA "
            "GPUs and their driver, CPUs, memory, disk) to uncomment and edit.",
            body=_template("check_working_environment.sh"),
        ),
    )


def experiment_run_templates() -> tuple[ScriptTemplate, ...]:
    """The experiment run templates: the experiment's command, run inside the activated experiment environment."""
    return (
        ScriptTemplate(
            key="command",
            label="Command",
            description="Run the experiment inside the activated experiment environment, "
            "writing stdout to a workspace log the verify script can read.",
            body=_template("experiment_run.sh"),
        ),
    )


def verify_templates() -> tuple[ScriptTemplate, ...]:
    """The verify-script templates for the standard verification cases.

    Verify scripts are plain POSIX sh, run from the workspace root after the
    run script, with nothing injected into their environment; the exit code is
    the verdict (0 = the declared validation passed). A later reproduction
    compares a fresh validated run with prior author evidence.
    """
    return (
        ScriptTemplate(
            key="stdout-contains",
            label="Stdout contains",
            description="The run log (stdout materialized to a file) must contain an expected phrase.",
            body=_template("verify_stdout_contains.sh"),
        ),
        ScriptTemplate(
            key="stdout-regex",
            label="Stdout matches regex",
            description="The run log must match an extended regular expression.",
            body=_template("verify_stdout_regex.sh"),
        ),
        ScriptTemplate(
            key="numeric-tolerance",
            label="Numeric within tolerance",
            description="A number extracted from the run log must be within ± epsilon of the claim.",
            body=_template("verify_numeric_tolerance.sh"),
        ),
        ScriptTemplate(
            key="file-sha256",
            label="Output file sha256",
            description="A produced file must hash to a recorded sha256 baseline.",
            body=_template("verify_file_sha256.sh"),
        ),
    )


def script_template_catalog() -> ScriptTemplateCatalog:
    """Every script kind's templates and where its scripts belong, each environment's default marked."""
    return ScriptTemplateCatalog(
        build_experiment_environment=BuildExperimentEnvironmentScriptTemplates(
            path=RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
            templates=_entries(build_templates()),
        ),
        activate_experiment_environment=ActivateExperimentEnvironmentScriptTemplates(
            path=RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
            templates=_entries(activate_experiment_environment_templates()),
        ),
        launch=LaunchScriptTemplates(path=RESERVED_LAUNCH_SCRIPT, templates=_entries(launch_templates())),
        check_working_environment=CheckWorkingEnvironmentScriptTemplates(
            path=RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT, templates=_entries(check_working_environment_templates())
        ),
        experiment=ExperimentScriptTemplates(
            run_script_path_pattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.sh",
            verify_script_path_pattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.verify.sh",
            templates=_entries(experiment_run_templates()),
        ),
        verify=_entries(verify_templates()),
    )


def _entries(templates: tuple[ScriptTemplate, ...]) -> list[ScriptTemplateEntry]:
    return [
        ScriptTemplateEntry(
            key=template.key,
            label=template.label,
            description=template.description,
            body=template.body,
            is_default=index == 0,
        )
        for index, template in enumerate(templates)
    ]

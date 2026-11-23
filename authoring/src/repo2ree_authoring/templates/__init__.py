from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files

from repo2ree_protocol.catalog import (
    ExperimentScriptTemplates,
    ReservedScriptTemplates,
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
    key: str
    label: str
    description: str
    body: str


def reserved_script_template(reserved_path: str) -> str:
    catalogs = {
        "build_experiment_environment.sh": build_templates,
        "activate_experiment_environment.sh": activate_experiment_environment_templates,
        "check_working_environment.sh": check_working_environment_templates,
        "launch.sh": launch_templates,
    }
    templates = catalogs[reserved_path.rsplit("/", 1)[-1]]()
    return templates[0].body


def build_templates() -> tuple[ScriptTemplate, ...]:
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
    return (
        ScriptTemplate(
            key="direct",
            label="Direct",
            description="Run each of the REE's scripts directly, where the runner puts it.",
            body=_template("launch_direct.sh"),
        ),
        ScriptTemplate(
            key="slurm",
            label="Slurm job step",
            description="Run each of the REE's scripts as a Slurm job step with the resources it needs, "
            "taking a reproducer's own options last.",
            body=_template("launch_slurm.sh"),
        ),
    )


def check_working_environment_templates() -> tuple[ScriptTemplate, ...]:
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
    return (
        ScriptTemplate(
            key="command",
            label="Command",
            description="Run the experiment inside the activated experiment environment, "
            "writing stdout to a workspace log the verify script can read.",
            body=_template("experiment_run.sh"),
        ),
    )


def experiment_verify_templates() -> tuple[ScriptTemplate, ...]:
    return (
        ScriptTemplate(
            key="none",
            label="No check",
            description="Verify nothing: the experiment counts as verified whenever its run script succeeds.",
            body=_template("verify_none.sh"),
        ),
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
    return ScriptTemplateCatalog(
        build_experiment_environment=ReservedScriptTemplates(
            path=RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, templates=_entries(build_templates())
        ),
        activate_experiment_environment=ReservedScriptTemplates(
            path=RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
            templates=_entries(activate_experiment_environment_templates()),
        ),
        launch=ReservedScriptTemplates(path=RESERVED_LAUNCH_SCRIPT, templates=_entries(launch_templates())),
        check_working_environment=ReservedScriptTemplates(
            path=RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT, templates=_entries(check_working_environment_templates())
        ),
        experiment_run=ExperimentScriptTemplates(
            path_pattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.sh", templates=_entries(experiment_run_templates())
        ),
        experiment_verify=ExperimentScriptTemplates(
            path_pattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.verify.sh",
            templates=_entries(experiment_verify_templates()),
        ),
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

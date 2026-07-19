"""Starter templates for the reserved, REE-owned overlay scripts.

Each template is a dedicated ``.sh`` file shipped inside this package — the
single source of truth for the starter content authors (human or agent) work
from. The build and activation templates are seeded into the overlay at REE
creation (``ReeStore.ensure_reserved_overlay_scripts``); the per-experiment run
and verify templates cannot be seeded (their paths only exist once an
experiment is named), so the API serves them for clients to prefill from.

Every script kind carries a catalog of named :class:`ScriptTemplate` variants,
one per standard case, so new strategies (a nix build, a bare-venv runtime, …)
slot in as further entries. Currently each run-script kind has a single
``docker`` variant. The first entry of a catalog is the default; for the
seeded scripts it is the content a fresh REE starts with.

Leaf module like ``reserved_paths``: it imports nothing from
``repo2ree_core``, so any layer can load templates without an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files


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
    """Return the default starter template for a seeded reserved script path.

    Catalogs are keyed by the script's file name, so the lookup is stable
    under renames of the reserved directory itself.
    """
    catalogs = {
        "build_script.sh": build_templates,
        "activation.sh": activation_templates,
    }
    return catalogs[reserved_path.rsplit("/", 1)[-1]]()[0].body


def build_templates() -> tuple[ScriptTemplate, ...]:
    """The build-script templates, one per runtime-packaging strategy."""
    return (
        ScriptTemplate(
            key="docker",
            label="Docker image",
            description="Build the project's Dockerfile into an image and save it as the runtime tarball.",
            body=_template("build_script_docker.sh"),
        ),
    )


def activation_templates() -> tuple[ScriptTemplate, ...]:
    """The activation run-script templates, one per runtime strategy."""
    return (
        ScriptTemplate(
            key="docker",
            label="Docker runtime",
            description="Load the saved runtime image and run a command inside it to prove the runtime works.",
            body=_template("activation_docker.sh"),
        ),
    )


def experiment_run_templates() -> tuple[ScriptTemplate, ...]:
    """The per-experiment run-script templates, one per runtime strategy."""
    return (
        ScriptTemplate(
            key="docker",
            label="Docker runtime",
            description="Load the saved runtime image and run the experiment inside it, "
            "teeing stdout to a workspace log the verify script can read.",
            body=_template("experiment_run_docker.sh"),
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

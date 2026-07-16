"""Starter templates for the reserved, REE-owned overlay scripts.

Each template is a dedicated ``.sh`` file shipped inside this package — the
single source of truth for the starter content authors (human or agent) work
from. The build and activation templates are seeded into the overlay at REE
creation (``ReeStore.ensure_reserved_overlay_scripts``); the per-experiment run
and verify templates cannot be seeded (their paths only exist once an
experiment is named), so the API serves them for clients to prefill from.

Leaf module like ``reserved_paths``: it imports nothing from
``repo2ree_core``, so any layer can load templates without an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files


def _template(name: str) -> str:
    return files(__package__).joinpath(name).read_text(encoding="utf-8")


def reserved_script_template(reserved_path: str) -> str:
    """Return the starter template for a reserved overlay script path.

    Templates are keyed by the script's file name, so the lookup is stable
    under renames of the reserved directory itself.
    """
    return _template(reserved_path.rsplit("/", 1)[-1])


def experiment_run_template() -> str:
    """Starter template for a per-experiment run script."""
    return _template("experiment_run.sh")


@dataclass(frozen=True)
class VerifyTemplate:
    """A prefilled verify-script template for one standard verification case.

    Verify scripts are plain POSIX sh, run from the workspace root after the
    run script, with nothing injected into their environment; the exit code is
    the verdict (0 = the claimed result was reproduced). Templates carry
    EDIT-ME placeholders the author fills in.
    """

    key: str
    label: str
    description: str
    body: str


def verify_templates() -> tuple[VerifyTemplate, ...]:
    """The verify-script templates for the standard cases; the first is the default."""
    return (
        VerifyTemplate(
            key="stdout-contains",
            label="Stdout contains",
            description="The run log (stdout materialized to a file) must contain an expected phrase.",
            body=_template("verify_stdout_contains.sh"),
        ),
        VerifyTemplate(
            key="stdout-regex",
            label="Stdout matches regex",
            description="The run log must match an extended regular expression.",
            body=_template("verify_stdout_regex.sh"),
        ),
        VerifyTemplate(
            key="numeric-tolerance",
            label="Numeric within tolerance",
            description="A number extracted from the run log must be within ± epsilon of the claim.",
            body=_template("verify_numeric_tolerance.sh"),
        ),
        VerifyTemplate(
            key="file-sha256",
            label="Output file sha256",
            description="A produced file must hash to a recorded sha256 baseline.",
            body=_template("verify_file_sha256.sh"),
        ),
    )

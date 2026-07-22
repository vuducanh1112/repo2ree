"""Checks for the build DAG's pip-requirements strategy branch.

Locational, like the dockerfile branch: ``requirements_at_project_root`` reads
*where* a requirements.txt is, never its contents — installing it is mechanical.

Building a venv from requirements.txt and packing it as the runtime artifact is
a repo2ree strategy (it settles conventions like where the venv lives), so the
strategy leaf is a confirmation-required ``candidate`` rather than an automatic
``complete``.
"""

from __future__ import annotations

from repo2ree_core.script_inference.models import (
    BindingKind,
    CheckResult,
    DecisionContext,
    PathMatchesObservation,
    ProjectRootBinding,
    RequirementsProjectBinding,
)


def _require_project_root(context: DecisionContext) -> None:
    binding = context.binding("project_root")
    if not isinstance(binding, ProjectRootBinding):
        raise ValueError("python check reached without a project_root binding")


class RequirementsAtProjectRootCheck:
    code = "requirements_at_project_root"
    label = "Is there a requirements.txt at the project root?"
    branches = frozenset({"none", "exactly_one"})
    requires: frozenset[BindingKind] = frozenset({"project_root"})
    produces: dict[str, frozenset[BindingKind]] = {
        "none": frozenset(),
        "exactly_one": frozenset({"requirements_project"}),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        _require_project_root(context)
        at_root = [r for r in context.facts.requirements_files if r.at_project_root]
        observed = PathMatchesObservation(count=len(at_root), paths=[r.path for r in at_root])
        # A directory holds at most one file named requirements.txt, so the only
        # cases are absent or the single root file.
        if not at_root:
            return CheckResult(branch="none", observed=observed)
        only = at_root[0]
        binding = RequirementsProjectBinding(requirements_path=only.path, digest=only.digest)
        return CheckResult(branch="exactly_one", observed=observed, bindings=(binding,))

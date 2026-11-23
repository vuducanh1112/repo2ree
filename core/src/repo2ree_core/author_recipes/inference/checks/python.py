from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.inference.models import BindingKind, CheckResult, DecisionContext
from repo2ree_protocol.inference import PathMatchesObservation, ProjectRootBinding, RequirementsProjectBinding


def _require_project_root(context: DecisionContext) -> None:
    binding = context.binding("project_root")
    if not isinstance(binding, ProjectRootBinding):
        raise ValueError("python check reached without a project_root binding")


class RequirementsAtProjectRootCheck:
    code = "requirements_at_project_root"
    label = "Is there a requirements.txt at the project root?"
    branches = frozenset({"none", "exactly_one"})
    requires: frozenset[BindingKind] = frozenset({"project_root"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "none": frozenset(),
        "exactly_one": frozenset({"requirements_project"}),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        _require_project_root(context)
        at_root = [r for r in context.facts.requirements_files if r.at_project_root]
        observed = PathMatchesObservation(count=len(at_root), paths=[r.path for r in at_root])
        if not at_root:
            return CheckResult(branch="none", observed=observed)
        only = at_root[0]
        binding = RequirementsProjectBinding(
            requirements_path=only.path, digest=only.digest, hash_locked=only.hash_locked
        )
        return CheckResult(branch="exactly_one", observed=observed, bindings=(binding,))

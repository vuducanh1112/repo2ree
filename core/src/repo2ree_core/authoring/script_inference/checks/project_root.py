"""The project-root prefix check.

``resolve_logical_root`` has already run inside the scan; this check reads its
result off ``RepositoryFacts`` and turns it into a typed ``project_root``
binding plus a safe-to-display observation. It is the shared prefix every
runtime strategy branch depends on.
"""

from __future__ import annotations

from repo2ree_core.authoring.script_inference.models import (
    BindingKind,
    CheckResult,
    DecisionContext,
    LogicalRootObservation,
    ProjectRootBinding,
)


class LogicalProjectRootCheck:
    code = "logical_project_root"
    label = "What is the logical project root?"
    branches = frozenset({"root", "wrapper"})
    requires: frozenset[BindingKind] = frozenset()
    produces: dict[str, frozenset[BindingKind]] = {
        "root": frozenset({"project_root"}),
        "wrapper": frozenset({"project_root"}),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        resolved = context.facts.logical_project_root
        is_root = resolved == "."
        branch = "root" if is_root else "wrapper"
        wrapper_depth = 0 if is_root else len(resolved.split("/"))
        binding = ProjectRootBinding(
            path=resolved,
            source="root" if is_root else "wrapper",
        )
        return CheckResult(
            branch=branch,
            observed=LogicalRootObservation(path=resolved, wrapper_depth=wrapper_depth),
            bindings=(binding,),
        )

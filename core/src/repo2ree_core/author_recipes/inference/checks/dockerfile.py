from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.inference.models import BindingKind, CheckResult, DecisionContext
from repo2ree_protocol.inference import DockerfileBinding, PathMatchesObservation, ProjectRootBinding


def _project_root(context: DecisionContext) -> str:
    binding = context.binding("project_root")
    if not isinstance(binding, ProjectRootBinding):
        raise ValueError("dockerfile check reached without a project_root binding")
    return binding.path


class DockerfilesAtProjectRootCheck:
    code = "dockerfiles_at_project_root"
    label = "How many Dockerfiles sit directly at the project root?"
    branches = frozenset({"none", "exactly_one", "more_than_one"})
    requires: frozenset[BindingKind] = frozenset({"project_root"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "none": frozenset(),
        "exactly_one": frozenset({"dockerfile"}),
        "more_than_one": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        root = _project_root(context)
        at_root = [d for d in context.facts.dockerfiles if d.at_project_root]
        paths = [d.path for d in at_root]
        observed = PathMatchesObservation(count=len(at_root), paths=paths)

        if len(at_root) == 0:
            return CheckResult(branch="none", observed=observed)
        if len(at_root) > 1:
            return CheckResult(branch="more_than_one", observed=observed)

        only = at_root[0]
        build_context = "." if root == "." else root
        binding = DockerfileBinding(
            path=only.path,
            build_context=build_context,
            digest=only.digest,
        )
        return CheckResult(branch="exactly_one", observed=observed, bindings=(binding,))


class NestedDockerfilesCheck:
    code = "nested_dockerfiles"
    label = "Are there Dockerfiles nested below the project root?"
    branches = frozenset({"none", "one_or_more"})
    requires: frozenset[BindingKind] = frozenset({"project_root"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "none": frozenset(),
        "one_or_more": frozenset(),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        nested = [d for d in context.facts.dockerfiles if not d.at_project_root]
        observed = PathMatchesObservation(count=len(nested), paths=[d.path for d in nested])
        branch = "none" if not nested else "one_or_more"
        return CheckResult(branch=branch, observed=observed)

"""Dockerfile-location checks for the build DAG's dockerfile strategy branch.

These checks are *purely locational*. ``docker build`` resolves ``FROM``,
``ARG``, and multi-stage itself, so the build command is mechanically
determined by a Dockerfile's path and the logical-root build context alone.
The only blocking conditions are structural — more than one project-root
Dockerfile (can't pick which), or a nested Dockerfile whose build context is
ambiguous. There is no ``FROM`` parsing here.
"""

from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.inference.models import (
    BindingKind,
    CheckResult,
    DecisionContext,
    DockerfileBinding,
    PathMatchesObservation,
    ProjectRootBinding,
)


def _project_root(context: DecisionContext) -> str:
    binding = context.binding("project_root")
    # Guaranteed present by the DAG's binding-dataflow validation.
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

"""Check-level fixtures: each input shape returns the exact branch, observation,
and produced bindings expected.

The check code is the shared vocabulary of the rule, the UI edge, and the test,
so decline tests are assertions about which branch a fixture takes.
"""

from __future__ import annotations

from typing import Literal

from repo2ree_core.author_recipes.inference.checks.dockerfile import (
    DockerfilesAtProjectRootCheck,
    NestedDockerfilesCheck,
)
from repo2ree_core.author_recipes.inference.checks.project_root import LogicalProjectRootCheck
from repo2ree_core.author_recipes.inference.models import (
    DecisionContext,
    DockerfileBinding,
    LogicalRootObservation,
    PathMatchesObservation,
    ProjectRootBinding,
)
from repo2ree_core.author_recipes.inference.policy import default_policy
from repo2ree_core.author_recipes.inference.repository_facts import DockerfileFact, RepositoryFacts


def _context(facts: RepositoryFacts, *, project_root: str | None = None) -> DecisionContext:
    bindings: tuple[ProjectRootBinding, ...] = ()
    if project_root is not None:
        source: Literal["root", "wrapper"] = "root" if project_root == "." else "wrapper"
        bindings = (ProjectRootBinding(path=project_root, source=source),)
    return DecisionContext(facts=facts, policy=default_policy(), bindings=bindings)


def test_logical_project_root_flat() -> None:
    facts = RepositoryFacts(logical_project_root=".")
    result = LogicalProjectRootCheck().evaluate(_context(facts))
    assert result.branch == "root"
    assert isinstance(result.observed, LogicalRootObservation)
    assert result.observed.path == "."
    assert result.observed.wrapper_depth == 0
    binding = result.bindings[0]
    assert isinstance(binding, ProjectRootBinding)
    assert binding.source == "root"


def test_logical_project_root_wrapper() -> None:
    facts = RepositoryFacts(logical_project_root="proj-main")
    result = LogicalProjectRootCheck().evaluate(_context(facts))
    assert result.branch == "wrapper"
    assert isinstance(result.observed, LogicalRootObservation)
    assert result.observed.wrapper_depth == 1
    binding = result.bindings[0]
    assert isinstance(binding, ProjectRootBinding)
    assert binding.source == "wrapper"


def _dockerfile(path: str, *, at_root: bool) -> DockerfileFact:
    return DockerfileFact(
        path=path,
        project_relative_path=path,
        digest="sha256:" + "0" * 64,
        at_project_root=at_root,
    )


def test_dockerfiles_at_root_exactly_one_produces_binding() -> None:
    facts = RepositoryFacts(
        logical_project_root=".",
        dockerfiles=[_dockerfile("Dockerfile", at_root=True)],
    )
    result = DockerfilesAtProjectRootCheck().evaluate(_context(facts, project_root="."))
    assert result.branch == "exactly_one"
    assert isinstance(result.observed, PathMatchesObservation)
    assert result.observed.count == 1
    binding = result.bindings[0]
    assert isinstance(binding, DockerfileBinding)
    assert binding.build_context == "."


def test_dockerfiles_at_root_wrapper_build_context() -> None:
    facts = RepositoryFacts(
        logical_project_root="proj-main",
        dockerfiles=[_dockerfile("proj-main/Dockerfile", at_root=True)],
    )
    result = DockerfilesAtProjectRootCheck().evaluate(_context(facts, project_root="proj-main"))
    assert result.branch == "exactly_one"
    binding = result.bindings[0]
    assert isinstance(binding, DockerfileBinding)
    assert binding.build_context == "proj-main"


def test_dockerfiles_at_root_none() -> None:
    facts = RepositoryFacts(logical_project_root=".")
    result = DockerfilesAtProjectRootCheck().evaluate(_context(facts, project_root="."))
    assert result.branch == "none"
    assert result.bindings == ()


def test_dockerfiles_at_root_more_than_one() -> None:
    facts = RepositoryFacts(
        logical_project_root=".",
        dockerfiles=[
            _dockerfile("Dockerfile", at_root=True),
            _dockerfile("Dockerfile.dev", at_root=True),
        ],
    )
    result = DockerfilesAtProjectRootCheck().evaluate(_context(facts, project_root="."))
    assert result.branch == "more_than_one"
    assert result.bindings == ()


def test_nested_dockerfiles_branch() -> None:
    facts = RepositoryFacts(
        logical_project_root=".",
        dockerfiles=[_dockerfile("docker/Dockerfile", at_root=False)],
    )
    result = NestedDockerfilesCheck().evaluate(_context(facts, project_root="."))
    assert result.branch == "one_or_more"
    assert isinstance(result.observed, PathMatchesObservation)
    assert result.observed.count == 1


def test_nested_dockerfiles_none() -> None:
    facts = RepositoryFacts(logical_project_root=".")
    result = NestedDockerfilesCheck().evaluate(_context(facts, project_root="."))
    assert result.branch == "none"

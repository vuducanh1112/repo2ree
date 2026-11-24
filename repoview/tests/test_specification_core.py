from __future__ import annotations

from repo2ree_repoview.overview.exports import SPEC_EXPORT, Spec, exported
from repo2ree_repoview.overview.pages.specification_core import invariant_is_core, page_specification_core


def current() -> Spec:
    return Spec.model_validate_json(exported(SPEC_EXPORT))


def test_a_rule_is_core_as_the_export_scopes_it() -> None:
    spec = current()
    core = {invariant.id for invariant in spec.invariants if invariant_is_core(spec, invariant)}

    assert "drift-is-found-by-the-next-attempt" in core
    assert "sealed-without-stale-evidence" in core
    assert "lost-executions-settle-their-attempt" not in core
    assert "follow-success-is-captured" not in core


def test_the_core_page_lists_the_core_rules_and_no_other() -> None:
    spec = current()
    body = page_specification_core(spec, {}).body

    for invariant in spec.invariants:
        assert (f">{invariant.id}<" in body) == invariant_is_core(spec, invariant)
    for rules in spec.documents.values():
        for rule in rules.rules:
            assert f">document:{rule.id}<" in body


def test_the_core_page_names_the_files_its_rules_come_from() -> None:
    body = page_specification_core(current(), {}).body

    for path in ("invariants.toml", "entities/attempt.toml", "documents/review.toml", "aggregates/ree.toml"):
        assert f"assurance/spec/{path}" in body
    assert "entities/execution.toml" not in body

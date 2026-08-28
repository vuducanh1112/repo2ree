"""What lint refuses to do.

The catalog's central policy is that only a script that cannot run at all
blocks. Everything else is advice, because these are the author's scripts. That
is a product decision rather than an implementation detail, so it is asserted
here directly rather than left implicit in each rule's fixtures.
"""

from __future__ import annotations

import pytest

from repo2ree_core.author_recipes.lint import lint_script
from repo2ree_core.author_recipes.lint.catalog import catalog_codes, make_finding
from repo2ree_core.author_recipes.lint.lint import CONTRACT_ONLY
from repo2ree_core.author_recipes.targets import ScriptTarget


def test_only_a_syntax_error_blocks() -> None:
    blocking = {code for code in catalog_codes() if make_finding(code, path="x").blocking}
    assert blocking == {"shell_syntax_error"}


def test_an_uncatalogued_code_cannot_be_emitted() -> None:
    # Rules name codes; the catalog owns what they mean. A rule that invents one
    # fails loudly rather than shipping a finding nobody defined.
    with pytest.raises(KeyError):
        make_finding("not_a_real_code", path="x")


def test_a_report_full_of_advice_is_still_ok() -> None:
    source = 'set --\ndocker run img main.py | tee "out"\n'
    report = lint_script(
        ScriptTarget(kind="experiment_run", path="ree-scripts/experiments/e.sh"),
        source,
        tiers=CONTRACT_ONLY,
    )
    assert len(report.findings) >= 2
    assert report.ok


def test_findings_are_ordered_deterministically() -> None:
    source = "EXPECTED='EDIT-ME a'\nB='EDIT-ME b'\nC='EDIT-ME c'\n"
    target = ScriptTarget(kind="experiment_verify", path="v.sh")
    first = lint_script(target, source, tiers=CONTRACT_ONLY)
    second = lint_script(target, source, tiers=CONTRACT_ONLY)
    assert first.model_dump() == second.model_dump()
    assert [f.line for f in first.findings] == [1, 2, 3]

"""The evidence graph is the specification's receipts, drawn: every dependency they state, and no other."""

from __future__ import annotations

import re

from repo2ree_repoview.overview.drawing import evidence_svg, stales
from repo2ree_repoview.overview.exports import SPEC_EXPORT, Aggregate, Spec, exported


def ree() -> Aggregate:
    return Spec.model_validate_json(exported(SPEC_EXPORT)).aggregates["Ree"]


def test_re_running_a_receipt_stales_everything_made_from_it() -> None:
    downstream = stales(ree())
    assert downstream["experiment_environment"] == ("experiment", "sbom", "sbom_cross_check", "test_activation")
    assert downstream["sbom"] == ("sbom_cross_check",)
    assert downstream["experiment"] == ()


def test_the_graph_draws_every_dependency_the_specification_states() -> None:
    aggregate = ree()
    svg = evidence_svg(aggregate)
    drawn = set(re.findall(r"<title>(.+?)&#45;&gt;(.+?)</title>", svg))
    stated = {
        (source, name)
        for name, receipt in aggregate.receipts.items()
        for source in (*receipt.made_from, *(f"field:{path}" for path in (*receipt.about, *receipt.rests_on)))
    }
    assert drawn == stated
    assert ("field:definition.workbench_environment", "experiment") in drawn
    assert ("field:definition.activate_experiment_environment", "test_activation") in drawn

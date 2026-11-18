"""The evidence graph is the specification's receipts, drawn: every dependency they state, and no other."""

from __future__ import annotations

import re

from repo2ree_repoview.overview.drawing import evidence_svg, stales
from repo2ree_repoview.overview.exports import SPEC_EXPORT, Aggregate, Spec, exported


def ree() -> Aggregate:
    return Spec.model_validate_json(exported(SPEC_EXPORT)).aggregates["Ree"]


def test_re_running_a_receipt_stales_everything_made_from_it() -> None:
    downstream = stales(ree())
    assert downstream["build_experiment_environment"] == (
        "activate_experiment_environment",
        "cross_check_sbom",
        "generate_sbom",
        "run_experiment",
    )
    assert downstream["activate_experiment_environment"] == ("run_experiment",)
    assert downstream["generate_sbom"] == ("cross_check_sbom",)
    assert downstream["run_experiment"] == ()


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
    assert ("field:definition.check_working_environment", "check_working_environment") in drawn
    assert ("field:definition.activate_experiment_environment", "activate_experiment_environment") in drawn
    assert ("activate_experiment_environment", "run_experiment") in drawn

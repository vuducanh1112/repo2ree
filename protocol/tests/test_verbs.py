"""Every command and read as the ``ree`` argv a workbench runs: what it writes, and only what was asked.

That ``ree`` reads each argv back as the same value is ``repo2ree_cli``'s to show (``cli/tests``).
"""

from __future__ import annotations

from repo2ree_protocol.command import (
    ReviewActivateExperimentEnvironmentArgs,
    ReviewActivateExperimentEnvironmentCommand,
    SuggestScriptsArgs,
    SuggestScriptsCommand,
    WriteScriptArgs,
    WriteScriptCommand,
)
from repo2ree_protocol.queries import CatQuery, InitRee, LintDraftQuery, ShowQuery, query_argv
from repo2ree_protocol.verbs import VERBS, command_types, to_argv


def test_every_command_has_a_verb_of_its_own() -> None:
    assert set(VERBS) == set(command_types())
    assert len(set(VERBS.values())) == len(VERBS)


def test_reads_keep_the_words_a_person_types() -> None:
    assert query_argv(ShowQuery(summary=True)) == (["show", "--summary"], None)
    assert query_argv(CatQuery(path="-odd name")) == (["cat", "--", "-odd name"], None)
    assert query_argv(InitRee(name="demo")) == (["init", "--name", "demo"], None)
    assert query_argv(LintDraftQuery(kind="experiment_run", experiment_name="fig", source="x")) == (
        ["lint-draft", "--experiment-name", "fig", "--", "experiment_run"],
        b"x",
    )


def test_an_argv_says_only_what_differs_from_the_defaults() -> None:
    cmd = WriteScriptCommand(args=WriteScriptArgs(path="ree-scripts/build_experiment_environment.sh", content="x"))
    assert to_argv(cmd) == (["write", "--", "ree-scripts/build_experiment_environment.sh"], b"x")


def test_a_target_is_its_kind_and_experiment() -> None:
    cmd = SuggestScriptsCommand(
        args=SuggestScriptsArgs.model_validate(
            {"targets": [{"kind": "build_experiment_environment"}, {"kind": "experiment_run", "experiment_name": "a"}]}
        )
    )
    assert to_argv(cmd)[0] == ["infer", "--target", "build_experiment_environment", "--target", "experiment_run:a"]


def test_a_review_step_names_its_review_by_option() -> None:
    cmd = ReviewActivateExperimentEnvironmentCommand(args=ReviewActivateExperimentEnvironmentArgs(review_id="review-1"))
    assert to_argv(cmd) == (["review", "test-activation", "--review-id", "review-1"], None)

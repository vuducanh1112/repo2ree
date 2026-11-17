"""Every command and read a workbench runs is what ``ree`` reads back from its argv: one value, two spellings."""

from __future__ import annotations

import string
from typing import Any, Literal, Union, cast, get_args, get_origin

import click
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import BaseModel

from repo2ree_cli.cli import read_back
from repo2ree_protocol.command import ScriptTargetSelectorArg, SealReeArgs, SealReeCommand
from repo2ree_protocol.queries import InitRee, LintDraftQuery, query_argv, query_types
from repo2ree_protocol.verbs import command_types, to_argv
from repo2ree_ree.primitives import LaunchOption
from repo2ree_ree.review import ReviewLaunch

pytestmark = pytest.mark.property

# Anything a process can be handed as an argument: no NUL, no lone surrogate.
_SURROGATES: tuple[Literal["Cs"]] = ("Cs",)
_TEXT = st.text(st.characters(exclude_categories=_SURROGATES, exclude_characters="\x00"), max_size=12)
_LAUNCH_OPTIONS = st.text(string.ascii_letters + string.digits + "-=,.:/", min_size=1, max_size=12)
_JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | _TEXT,
    lambda inner: st.lists(inner, max_size=3) | st.dictionaries(_TEXT, inner, max_size=3),
    max_leaves=6,
)


def _for(annotation: Any) -> st.SearchStrategy[Any]:
    origin = get_origin(annotation)
    if annotation is ReviewLaunch:
        return st.one_of(
            st.just(ReviewLaunch(mode="native")),
            st.builds(
                ReviewLaunch,
                mode=st.just("author"),
                options=st.lists(_LAUNCH_OPTIONS.map(LaunchOption), max_size=3).map(tuple),
            ),
        )
    if annotation is ScriptTargetSelectorArg:
        # An experiment's script is named for its experiment; no other script is.
        return st.one_of(
            st.builds(
                ScriptTargetSelectorArg,
                kind=st.sampled_from(["experiment_run", "experiment_verify"]),
                experiment_name=_TEXT.filter(bool),
            ),
            st.builds(
                ScriptTargetSelectorArg,
                kind=st.sampled_from(
                    [
                        "build_experiment_environment",
                        "activate_experiment_environment",
                        "launch",
                        "check_working_environment",
                    ]
                ),
            ),
        )
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _model(annotation)
    if annotation is bool:
        return st.booleans()
    if annotation is str:
        return _TEXT
    if origin is Literal:
        return st.sampled_from(get_args(annotation))
    if origin in (Union, type(int | None)):
        return st.one_of(*(_for(arg) for arg in get_args(annotation)))
    if annotation is type(None):
        return st.none()
    if origin in (list, tuple):
        items = st.lists(_for(get_args(annotation)[0]), max_size=3)
        return items if origin is list else items.map(tuple)
    if origin is dict:
        return st.dictionaries(_TEXT, _JSON, max_size=3)
    raise TypeError(f"no strategy for {annotation!r}")


def _model(model: type[BaseModel]) -> st.SearchStrategy[BaseModel]:
    fields = {
        # A field that must not be empty, an image reference say, is never drawn empty.
        name: _for(info.annotation).filter(lambda value: value != "")
        if any(getattr(item, "min_length", 0) for item in info.metadata)
        else _for(info.annotation)
        for name, info in model.model_fields.items()
    }
    return st.fixed_dictionaries(fields).map(model.model_validate)


def _command(command: type[BaseModel]) -> st.SearchStrategy[BaseModel]:
    args = cast(type[BaseModel], command.model_fields["args"].annotation)
    return _model(args).map(lambda value: command.model_validate({"args": value}))


def _read(model: type[BaseModel]) -> st.SearchStrategy[BaseModel]:
    if model is LintDraftQuery:
        # An experiment's script is named for its experiment; no other script is.
        return st.one_of(
            st.builds(
                LintDraftQuery,
                kind=st.sampled_from(["experiment_run", "experiment_verify"]),
                experiment_name=_TEXT.filter(bool),
                experiment_environment_path=st.none() | _TEXT,
                source=_TEXT,
            ),
            st.builds(
                LintDraftQuery,
                kind=st.sampled_from(
                    [
                        "build_experiment_environment",
                        "activate_experiment_environment",
                        "launch",
                        "check_working_environment",
                    ]
                ),
                experiment_environment_path=st.none() | _TEXT,
                source=_TEXT,
            ),
        )
    return _model(model)


@pytest.mark.parametrize("command", command_types(), ids=lambda command: command.__name__)
@settings(max_examples=60, deadline=None)
@given(data=st.data())
def test_a_command_read_back_from_its_argv_is_the_command(command: type[BaseModel], data: st.DataObject) -> None:
    cmd = data.draw(_command(command))
    argv, stdin = to_argv(cmd)  # type: ignore[arg-type]
    assert read_back(argv, stdin) == cmd


@pytest.mark.parametrize("read", [*query_types(), InitRee], ids=lambda read: read.__name__)
@settings(max_examples=60, deadline=None)
@given(data=st.data())
def test_a_read_read_back_from_its_argv_is_the_read(read: type[BaseModel], data: st.DataObject) -> None:
    value = data.draw(_read(read))
    argv, stdin = query_argv(value)
    assert read_back(argv, stdin) == value


def test_a_bare_seal_includes_the_source_the_experiment_environment_and_the_results() -> None:
    assert read_back(["seal-ree"]) == SealReeCommand(
        args=SealReeArgs(source_included=True, experiment_environment_included=True, results_included=True)
    )
    assert read_back(["seal-ree", "--no-results-included"]) == SealReeCommand(args=SealReeArgs(results_included=False))


def test_an_option_takes_its_value_after_an_equals_sign_too() -> None:
    assert read_back(["acquire-source", "--mode=download", "--origin-url=https://x/y.git"]) == read_back(
        ["acquire-source", "--mode", "download", "--origin-url", "https://x/y.git"]
    )


@pytest.mark.parametrize(
    ("argv", "stdin", "problem"),
    [
        (["no-such-verb"], None, "No such command"),
        (["run-experiment"], None, "experiment_name"),
        (["seal-ree", "--no-such-option"], None, "No such option"),
        (["write-script", "--", "a.sh"], None, "read from stdin"),
        (["acquire-source", "--mode"], None, "requires an argument"),
        (["review", "acquire-source", "--basis", "nope"], None, "'nope' is not one of"),
        (["suggest-scripts", "--target", "nope"], None, "no script kind"),
        (["suggest-scripts", "--target", "experiment_run"], None, "requires an experiment_name"),
    ],
)
def test_words_that_spell_no_command_say_why(argv: list[str], stdin: bytes | None, problem: str) -> None:
    with pytest.raises(click.UsageError, match=problem):
        read_back(argv, stdin)

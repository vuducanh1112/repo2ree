"""Every command and its ``ree`` argv are two spellings of one value."""

from __future__ import annotations

import string
from typing import Any, Literal, Union, cast, get_args, get_origin

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import BaseModel

from repo2ree_protocol.argv import ArgvError
from repo2ree_protocol.command import (
    GenerateScriptCandidatesArgs,
    GenerateScriptCandidatesCommand,
    ScriptTargetSelectorArg,
    WriteFileArgs,
    WriteFileCommand,
)
from repo2ree_protocol.verbs import VERBS, command_types, from_argv, to_argv
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
                kind=st.sampled_from(["build_experiment_environment", "activate_experiment_environment", "launch"]),
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
    fields = {name: _for(info.annotation) for name, info in model.model_fields.items()}
    return st.fixed_dictionaries(fields).map(model.model_validate)


def _command(command: type[BaseModel]) -> st.SearchStrategy[BaseModel]:
    args = cast(type[BaseModel], command.model_fields["args"].annotation)
    return _model(args).map(lambda value: command.model_validate({"args": value}))


def test_every_command_has_a_verb_of_its_own() -> None:
    assert set(VERBS) == set(command_types())
    assert len(set(VERBS.values())) == len(VERBS)


@pytest.mark.parametrize("command", command_types(), ids=lambda command: command.__name__)
@settings(max_examples=60, deadline=None)
@given(data=st.data())
def test_a_command_read_back_from_its_argv_is_the_command(command: type[BaseModel], data: st.DataObject) -> None:
    cmd = data.draw(_command(command))
    argv, stdin = to_argv(cmd)  # type: ignore[arg-type]
    assert from_argv(argv, stdin) == cmd


def test_an_argv_says_only_what_differs_from_the_defaults() -> None:
    cmd = WriteFileCommand(args=WriteFileArgs(path="ree-scripts/build_experiment_environment.sh", content="x"))
    assert to_argv(cmd) == (["write", "--", "ree-scripts/build_experiment_environment.sh"], b"x")


def test_a_target_is_its_kind_and_experiment() -> None:
    cmd = GenerateScriptCandidatesCommand(
        args=GenerateScriptCandidatesArgs.model_validate(
            {"targets": [{"kind": "build_experiment_environment"}, {"kind": "experiment_run", "experiment_name": "a"}]}
        )
    )
    assert to_argv(cmd)[0] == ["infer", "--target", "build_experiment_environment", "--target", "experiment_run:a"]


@pytest.mark.parametrize(
    ("argv", "stdin", "problem"),
    [
        (["no-such-verb"], None, "no command"),
        (["experiment"], None, "expected 1 argument"),
        (["seal", "--no-such-option"], None, "takes no option"),
        (["write", "--", "a.sh"], None, "read from stdin"),
        (["acquire-source", "--mode"], None, "needs a value"),
    ],
)
def test_words_that_spell_no_command_say_why(argv: list[str], stdin: bytes | None, problem: str) -> None:
    with pytest.raises(ArgvError, match=problem):
        from_argv(argv, stdin)

"""Every read of an REE, and its creation, as the words a caller runs.

A read is a typed value, as a command is: the workbench is sent one, not an argv, and spells it as the ``ree`` argv
that answers it (``query_argv``), which the command line reads back (``query_from_argv``). Both follow from the
models (``repo2ree_protocol.argv``), so the spellings cannot drift, and what a workbench is sent can only be a read.
Each read names the model its answer on stdout is (``REPLIES``); ``cat`` and ``bundle`` answer with bytes.
"""

from __future__ import annotations

from typing import Annotated, Literal, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_protocol.argv import POSITIONAL, STDIN, VERB, ArgvError, decode_args, encode_args
from repo2ree_protocol.catalog import ScriptTemplateCatalog
from repo2ree_protocol.command import ScriptTargetSelectorArg, TargetKind
from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_protocol.history import OperationHistory
from repo2ree_protocol.lint import LintReport, ScriptDeclarations
from repo2ree_ree.model import Ree
from repo2ree_ree.review import ReviewSet


class _Query(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ManifestQuery(_Query):
    """Print the REE's record (ree.json)."""

    query: Annotated[Literal["manifest"], VERB] = "manifest"


class ShowQuery(_Query):
    """Print the REE as a document: its definition, evidence, audit, steps and files."""

    query: Annotated[Literal["show"], VERB] = "show"
    # Leave out the files' contents.
    summary: bool = False


class ReviewsQuery(_Query):
    """Print the REE's reviews, newest first."""

    query: Annotated[Literal["reviews"], VERB] = "reviews"


class LogQuery(_Query):
    """Print every attempt recorded in the REE's history and its reviews'."""

    query: Annotated[Literal["log"], VERB] = "log"


class CatQuery(_Query):
    """Write the bytes of PATH, a file anywhere in the REE, to stdout."""

    query: Annotated[Literal["cat"], VERB] = "cat"
    path: Annotated[str, POSITIONAL]


class BundleQuery(_Query):
    """Write the REE's portable bundle, with its histories, to stdout."""

    query: Annotated[Literal["bundle"], VERB] = "bundle"


class TemplatesQuery(_Query):
    """Print the starter templates for the REE's scripts and where each script belongs."""

    query: Annotated[Literal["templates"], VERB] = "templates"


class LintDraftQuery(_Query):
    """Check the unsaved script on stdin as the REE's KIND script, by the checks that run no process."""

    query: Annotated[Literal["lint-draft"], VERB] = "lint-draft"
    kind: Annotated[TargetKind, POSITIONAL]
    # The experiment the script is for.
    experiment_name: str | None = None
    # The experiment environment's path the script is checked against.
    experiment_environment_path: str | None = None
    source: Annotated[str, STDIN]

    @model_validator(mode="after")
    def _names_its_target(self) -> LintDraftQuery:
        ScriptTargetSelectorArg(kind=self.kind, experiment_name=self.experiment_name)
        return self

    @property
    def target(self) -> ScriptTargetSelectorArg:
        return ScriptTargetSelectorArg(kind=self.kind, experiment_name=self.experiment_name)

    @property
    def declarations(self) -> ScriptDeclarations:
        return ScriptDeclarations(experiment_environment_path=self.experiment_environment_path)


Query = Annotated[
    ManifestQuery | ShowQuery | ReviewsQuery | LogQuery | CatQuery | BundleQuery | TemplatesQuery | LintDraftQuery,
    Field(discriminator="query"),
]

# The model each read's answer on stdout is; None for one that answers with bytes.
REPLIES: dict[type[BaseModel], type[BaseModel] | None] = {
    ManifestQuery: Ree,
    ShowQuery: WorkbenchReeDocument,
    ReviewsQuery: ReviewSet,
    LogQuery: OperationHistory,
    CatQuery: None,
    BundleQuery: None,
    TemplatesQuery: ScriptTemplateCatalog,
    LintDraftQuery: LintReport,
}


class InitRee(BaseModel):
    """Create an REE here (or at -C) and capture its first version; again, it keeps what is there.

    With --oci, every script runs in that OCI image, and the REE starts with the scripts that suit one; without,
    they run on the machine that runs each step.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    init: Annotated[Literal["init"], VERB] = "init"
    name: str
    # The working environment: the OCI image the REE's scripts run in, which decides the scripts it starts with.
    oci: str | None = Field(default=None, min_length=1)


def query_types() -> tuple[type[BaseModel], ...]:
    """Every member of the ``Query`` union."""
    return cast(tuple[type[BaseModel], ...], get_args(get_args(Query)[0]))


def verb_of(model: type[BaseModel]) -> str:
    """The verb that spells a read, or ``init``: the default of its first field."""
    return cast(str, next(iter(model.model_fields.values())).default)


def query_argv(query: BaseModel) -> tuple[list[str], bytes | None]:
    """The argv after ``ree`` that answers ``query`` (or runs ``init``), and what it reads on stdin."""
    words, stdin = encode_args(query)
    return [verb_of(type(query)), *words], stdin


def query_from_argv(argv: list[str], stdin: bytes | None = None) -> BaseModel:
    """The read (or ``init``) an argv after ``ree`` spells."""
    models: tuple[type[BaseModel], ...] = (*query_types(), InitRee)
    for model in models:
        if argv[:1] == [verb_of(model)]:
            return decode_args(model, argv[1:], stdin)
    raise ArgvError(f"no read {argv[:1]!r}")

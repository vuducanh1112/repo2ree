"""``ree``: every command on an REE, for a person at a terminal, an agent, and a workbench alike.

Each command runs against the REE at ``-C`` or, without it, the nearest one at or above the current directory, and
ends in one result (``ActionResult``): a person reads it as plain lines, and ``--json`` prints it as one JSON line on
stdout, with the run's log events as NDJSON on stderr. ``cat``, ``bundle`` and ``completion`` print what they are
asked for instead. The exit status says how it ended (``EXIT_CODES``).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast
from uuid import uuid4

import click
from click.shell_completion import get_completion_class
from pydantic import BaseModel, JsonValue

from repo2ree_authoring.lint import CONTRACT_ONLY, lint_script
from repo2ree_authoring.targets import resolve_target
from repo2ree_authoring.templates import script_template_catalog
from repo2ree_cli import render, signing
from repo2ree_cli.models import (
    CancelRequested,
    Initialized,
    ReviewRun,
    ScriptEdited,
    ScriptWritten,
    StepRun,
    Waited,
)
from repo2ree_cli.options import EXPERIMENT_KINDS, KINDS, TARGET, Spelling, read_stdin
from repo2ree_cli.schema import ReeCommand, describe
from repo2ree_core.bundle.download import materialized_ree_download
from repo2ree_core.domain.ree.steps import REE_STEPS
from repo2ree_core.domain.ree.transitions import revision_of
from repo2ree_core.evidence.review.store import load_reviews, read_review_record
from repo2ree_core.execution.working_environment import machine_facts
from repo2ree_core.operations.capture import settle_interrupted
from repo2ree_core.operations.handlers.author.file_concurrency import workspace_content_etag
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.read_models.files import read_ree_file_bytes
from repo2ree_core.operations.read_models.ree_document import get_ree_document, get_ree_status, get_ree_steps
from repo2ree_core.operations.session import request_cancel, run_session
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.persistence.run_lock import running_run, wait_until_free
from repo2ree_protocol.build import current_build
from repo2ree_protocol.command import (
    AcquireSourceCommand,
    Command,
    LoadReeBundleCommand,
    PatchReeDefinitionCommand,
    ReviewAcquireSourceArgs,
    ReviewAcquireSourceCommand,
    ReviewActivateExperimentEnvironmentCommand,
    ReviewBuildExperimentEnvironmentCommand,
    ReviewRunExperimentCommand,
    ScriptTargetSelectorArg,
    SealReeCommand,
    SignReeArgs,
    SignReeCommand,
    SignReviewCommand,
    SuggestScriptsCommand,
    TargetKind,
    WriteScriptArgs,
    WriteScriptCommand,
    command_adapter,
)
from repo2ree_protocol.document import ReeStatusReport, WorkbenchReeDocument
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.history import OperationHistory
from repo2ree_protocol.inference import InferenceReport
from repo2ree_protocol.machine import MachineFacts
from repo2ree_protocol.outputs import (
    OUTPUTS,
    AcquireSourceOutputs,
    BuildExperimentEnvironmentOutputs,
    CrossCheckSbomOutputs,
    EvaluateOutputs,
    GenerateSbomOutputs,
    LoadReeBundleOutputs,
    ObserveHardwareOutputs,
    PatchReeDefinitionOutputs,
    ReviewAcquireSourceOutputs,
    ReviewActivateExperimentEnvironmentOutputs,
    ReviewBuildExperimentEnvironmentOutputs,
    ReviewRunExperimentOutputs,
    RunnableOperationOutputs,
    SealOutputs,
    SignOutputs,
    SignReviewOutputs,
    outputs_of,
)
from repo2ree_protocol.queries import (
    REPLIES,
    BundleQuery,
    CatQuery,
    InitRee,
    LintDraftQuery,
    LogQuery,
    ManifestQuery,
    ReviewsQuery,
    ShowQuery,
    TemplatesQuery,
    verb_of,
)
from repo2ree_protocol.result import ActionResult, FailureCategory
from repo2ree_protocol.verbs import REVIEW, SUMMARIES, VERBS
from repo2ree_ree.layout import REE_MANIFEST, SIGNATURES
from repo2ree_ree.primitives import Digest
from repo2ree_ree.review import ReviewSet
from repo2ree_ree.signature import PREDICATE_TYPES, REVIEW_PREDICATE_TYPE, SIGNATURE_SUFFIX, review_signature_path
from repo2ree_ree.verification import SignatureVerifications, Signer, VerificationPolicy, VerifiedClaim
from repo2ree_telemetry.command_line import (
    invocation_span,
    name_invocation,
    record_invocation_result,
    setup_command_line_telemetry,
)

SUCCEEDED = 0
FAILED = 1
# A command refused for what was asked, as for a command line that spells none.
REFUSED = 2
# A run that was canceled, as a shell reports one stopped by SIGINT.
CANCELED = 130
_REFUSALS: tuple[FailureCategory, ...] = ("validation", "precondition", "conflict")
EXIT_CODES = {
    SUCCEEDED: "succeeded",
    FAILED: "failed: a script, a process or ree itself (execution, timeout, unavailable, internal)",
    REFUSED: "refused for what was asked: a usage error, or validation, precondition or conflict",
    CANCELED: "canceled",
}
# Where a staged archive comes from on the command line; the commands themselves name it by its upload token.
ARCHIVE_OPTION = "--archive"
BUNDLE_OPTION = "--bundle"
# What a bundle signed by `ree sign-ree` itself is called while it is staged.
SIGNED_HERE = "signed.sigstore.json"


# ================================================
# The invocation, and how a result ends it
# ================================================


class NoReeError(Exception):
    """The command needs an REE, and there is none where it looked."""


@dataclass(frozen=True)
class Invocation:
    """What the options before the command say: the REE, the output form, and the run's identity."""

    ree: Path | None
    machine: bool
    run_id: str | None
    context: ExecutionContext | None
    result_file: Path | None = None

    def layout(self) -> ReeLayout:
        """The REE at ``-C`` or, without it, the nearest one at or above the current directory."""
        if self.ree is not None:
            if not (self.ree / REE_MANIFEST).is_file():
                raise NoReeError(f"no REE at {self.ree}: create one with `ree -C {self.ree} initialize-ree`")
            return ReeLayout(root=self.ree)
        found = nearest_ree(Path.cwd())
        if found is None:
            raise NoReeError(
                f"no REE at or above {Path.cwd()}: create one with `ree initialize-ree`, or name one with -C"
            )
        return ReeLayout(root=found)

    def sink(self) -> LogSink:
        return _ndjson_sink if self.machine else _plain_sink

    def identity(self, step: int | None = None) -> tuple[ExecutionContext, str]:
        """The context and run id of a run; ``step`` numbers it among the commands one invocation runs."""
        if step is None:
            context = self.context or ExecutionContext.new()
            return context, self.run_id or f"manual-{context.attempt_id}"
        context = ExecutionContext.new()
        return context, f"{self.run_id}.{step}" if self.run_id else f"manual-{context.attempt_id}"

    def run(
        self, cmd: Command, layout: ReeLayout, *, identity: tuple[ExecutionContext, str] | None = None
    ) -> ActionResult:
        """Run ``cmd`` in its own session, as the run ``identity`` names, by default the invocation's."""
        context, run_id = identity or self.identity()
        if self.machine:
            started = {"type": "started", "run_id": run_id, "operation": str(cmd.operation)}
            click.echo(json.dumps(started), err=True)
        return run_session(
            cmd,
            layout=layout,
            emit=self.sink(),
            run_id=run_id,
            context=context,
        )


def nearest_ree(start: Path) -> Path | None:
    """The nearest directory at or above ``start`` that holds an REE."""
    return next((path for path in (start, *start.parents) if (path / REE_MANIFEST).is_file()), None)


def _ndjson_sink(stream: str, level: str, message: str) -> None:
    click.echo(json.dumps({"type": "log", "stream": stream, "level": level, "message": message}), err=True)


def _plain_sink(stream: str, level: str, message: str) -> None:
    if stream == "system":
        click.echo(click.style(message, dim=level == "info", fg="red" if level == "error" else None), err=True)
    else:
        click.echo(message, err=True)


def _invocation() -> Invocation:
    return click.get_current_context().find_object(Invocation)  # type: ignore[return-value]


def finish(
    invocation: Invocation,
    words: str,
    result: ActionResult,
    *,
    render_with: Callable[[dict[str, Any]], str] | None = None,
    ran: bool = False,
) -> NoReturn:
    """Print ``result`` as the invocation asks and exit with the status it calls for.

    ``ran`` says a command ran, whose outcome a person is told on stderr beside its outputs.
    """
    record_invocation_result(result)
    if invocation.result_file is not None:
        invocation.result_file.write_text(result.model_dump_json() + "\n", encoding="utf-8")
    if invocation.machine:
        click.echo(result.model_dump_json())
    else:
        if result.status == "succeeded" and result.outputs:
            text = render_with(result.outputs) if render_with else render.outputs(result.outputs)
            if text:
                click.echo(text)
        if result.failure is not None:
            click.echo(click.style(f"{words} failed: {result.failure.message}", fg="red"), err=True)
            if result.failure.category == "precondition" and (hint := _hint(invocation)):
                click.echo(hint, err=True)
        elif ran or result.status == "canceled":
            click.echo(click.style(f"{words} {result.status}", dim=True), err=True)
    sys.exit(exit_code(result))


def exit_code(result: ActionResult) -> int:
    if result.status == "succeeded":
        return SUCCEEDED
    if result.status == "canceled":
        return CANCELED
    return REFUSED if result.failure and result.failure.category in _REFUSALS else FAILED


def refuse(invocation: Invocation, words: str, category: FailureCategory, message: str) -> NoReturn:
    finish(invocation, words, ActionResult.failed(category, message, origin="executor"))


def answer(invocation: Invocation, words: str, outputs: BaseModel | dict[str, Any], **kwargs: Any) -> NoReturn:
    """End a command that ran nothing in the REE with what it found."""
    data = outputs.model_dump(mode="json") if isinstance(outputs, BaseModel) else outputs
    finish(invocation, words, ActionResult(status="succeeded", outputs=data), **kwargs)


def _hint(invocation: Invocation) -> str | None:
    try:
        return render.next_hint(get_ree_steps(invocation.layout()))
    except (NoReeError, FileNotFoundError):
        return None


def _layout_or_refuse(invocation: Invocation, words: str) -> ReeLayout:
    try:
        return invocation.layout()
    except NoReeError as exc:
        refuse(invocation, words, "precondition", str(exc))


# ================================================
# The command line
# ================================================


class ReeGroup(click.Group):
    """A command group: under ``--json`` a usage error is a refused result too, so an agent reads one shape.

    The invocation's span is named after the command it resolves to.
    """

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        name, command, rest = super().resolve_command(ctx, args)
        if name is not None and not isinstance(command, click.Group):
            groups = [each.info_name or "" for each in _lineage(ctx) if each.parent is not None]
            name_invocation([*groups, name])
        return name, command, rest

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except click.UsageError as exc:
            if not ctx.params.get("machine"):
                raise
            failed = ActionResult.failed("validation", exc.format_message(), origin="executor")
            click.echo(failed.model_dump_json())
            ctx.exit(REFUSED)


def _lineage(ctx: click.Context) -> list[click.Context]:
    return [*_lineage(ctx.parent), ctx] if ctx.parent is not None else [ctx]


_EPILOG = "\b\nExit status:\n" + "\n".join(f"  {code:>3}  {meaning}" for code, meaning in EXIT_CODES.items())


@click.group(cls=ReeGroup, context_settings={"help_option_names": ["-h", "--help"]}, epilog=_EPILOG)
@click.option(
    "-C",
    "ree",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="The REE's directory; by default the nearest one at or above the current directory.",
)
@click.option(
    "--json",
    "machine",
    is_flag=True,
    help="Print the result as one JSON line on stdout, and the run's log as NDJSON on stderr.",
)
@click.option("--run-id", default=None, hidden=True, help="The run's id, which names its log in runs/.")
@click.option("--context", default=None, hidden=True, help="The run's invocation identity, as JSON.")
@click.option(
    "--result-file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    hidden=True,
    help="Also write the result, as --json prints it, to this file.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    ree: Path | None,
    machine: bool,
    run_id: str | None,
    context: str | None,
    result_file: Path | None,
) -> None:
    """repo2ree: author, run, seal and review reproducible execution environments (REEs).

    Start with `ree initialize-ree`, then `ree status` says where the REE stands and what to run next.
    """
    ctx.obj = Invocation(
        ree=ree.resolve() if ree else None,
        machine=machine,
        run_id=run_id,
        context=ExecutionContext.model_validate_json(context) if context else None,
        result_file=result_file,
    )


def main() -> None:
    shutdown = setup_command_line_telemetry("repo2ree-cli", sys.stderr)
    # Where the workbench gives the command line its pinned tools (git, curl, tar, …): first on PATH for it and the
    # processes it starts, while anything else keeps the PATH it had.
    if tools_bin := os.environ.get("REPO2REE_TOOLS_BIN"):
        os.environ["PATH"] = f"{tools_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    try:
        with invocation_span():
            cli()
    finally:
        shutdown()


@cli.group(REVIEW, cls=ReeGroup)
def review() -> None:
    """Review a sealed REE: reproduce its steps in a review of their own and compare them with the author's.

    `ree review all` runs every step. A step names its review with --review-id; without it, `acquire-source` opens a
    new review and the other steps continue the newest one.
    """


# ================================================
# Commands that run in the REE
# ================================================

Params = dict[str, Any]
Handler = Callable[[Invocation, tuple[str, ...], type[BaseModel], Spelling, Params], None]


def _args_of(command: type[BaseModel]) -> type[BaseModel]:
    return cast(type[BaseModel], command.model_fields["args"].annotation)


def _run_verb(
    invocation: Invocation,
    words: tuple[str, ...],
    command: type[BaseModel],
    spelling: Spelling,
    params: Params,
    **filled: Any,
) -> None:
    layout = _layout_or_refuse(invocation, " ".join(words))
    args = spelling.build(params, read_stdin(spelling.model), **filled)
    _run_and_finish(invocation, words, command.model_validate({"args": args}), layout)  # type: ignore[arg-type]


def _run_and_finish(invocation: Invocation, words: tuple[str, ...], cmd: Command, layout: ReeLayout) -> NoReturn:
    result = invocation.run(cmd, layout)
    finish(
        invocation,
        " ".join(words),
        result,
        render_with=lambda _outputs: _shown(outputs_of(str(cmd.operation), result), layout),
        ran=True,
    )


type _ReviewStepOutputs = (
    ReviewAcquireSourceOutputs
    | ReviewBuildExperimentEnvironmentOutputs
    | ReviewActivateExperimentEnvironmentOutputs
    | ReviewRunExperimentOutputs
)


def _shown(outputs: BaseModel, layout: ReeLayout) -> str:
    """What a person is shown of a command's outputs: what it found, not every receipt and digest it recorded."""
    match outputs:
        case (
            ReviewAcquireSourceOutputs()
            | ReviewBuildExperimentEnvironmentOutputs()
            | ReviewActivateExperimentEnvironmentOutputs()
            | ReviewRunExperimentOutputs()
        ):
            return _review_shown(outputs, layout)
        case AcquireSourceOutputs():
            return render.acquired(outputs)
        case PatchReeDefinitionOutputs():
            return render.patched(outputs)
        case EvaluateOutputs():
            return render.evaluation(outputs)
        case ObserveHardwareOutputs():
            return render.hardware(outputs)
        case RunnableOperationOutputs():
            return render.ran(outputs)
        case BuildExperimentEnvironmentOutputs():
            return render.built(outputs)
        case GenerateSbomOutputs():
            return render.sbom(outputs)
        case CrossCheckSbomOutputs():
            return render.cross_checked(outputs)
        case SealOutputs():
            return render.sealed(outputs)
        case SignOutputs() | SignReviewOutputs():
            return render.signed(outputs)
        case LoadReeBundleOutputs():
            return render.loaded(outputs)
    return render.outputs(outputs.model_dump(mode="json"))


def _review_shown(outputs: _ReviewStepOutputs, layout: ReeLayout) -> str:
    """The review as the step left it: each comparison so far."""
    record = next((item for item in load_reviews(layout).reviews if item.review_id == outputs.review_id), None)
    return render.review(record) if record is not None else outputs.review_id


def _acquire_source(
    invocation: Invocation, words: tuple[str, ...], command: type[BaseModel], spelling: Spelling, params: Params
) -> None:
    layout = _layout_or_refuse(invocation, " ".join(words))
    filled: dict[str, Any] = {}
    if params["archive"] is not None:
        filled = {**_staged(layout, params["archive"]), "mode": "upload"}
    elif params["origin_url"]:
        filled = {"mode": "download"}
    elif params["mode"] is None:
        raise click.UsageError(f"give {ARCHIVE_OPTION} PATH or --origin-url URL")
    args = spelling.build(params, None, **filled)
    _run_and_finish(invocation, words, AcquireSourceCommand.model_validate({"args": args}), layout)


def _load_bundle(
    invocation: Invocation, words: tuple[str, ...], command: type[BaseModel], spelling: Spelling, params: Params
) -> None:
    layout = _layout_or_refuse(invocation, " ".join(words))
    if params["archive"] is None and params["upload_token"] is None:
        raise click.UsageError(f"give {ARCHIVE_OPTION} PATH")
    filled = _staged(layout, params["archive"]) if params["archive"] is not None else {}
    args = spelling.build(params, None, **filled)
    _run_and_finish(invocation, words, LoadReeBundleCommand.model_validate({"args": args}), layout)


def _sign(
    invocation: Invocation, words: tuple[str, ...], command: type[BaseModel], spelling: Spelling, params: Params
) -> None:
    """Sign the seal, or a review of it, with Sigstore here, or add a bundle signed elsewhere (``--bundle``)."""
    layout = _layout_or_refuse(invocation, " ".join(words))
    if params["bundle"] is not None:
        filled = _staged(layout, params["bundle"])
    elif params["upload_token"] is not None:
        filled = {}
    else:
        statement = (
            _review_statement(invocation, " ".join(words), layout, params["review_id"])
            if command is SignReviewCommand
            else _seal_statement(invocation, " ".join(words), layout, params)
        )
        filled = _staged_bytes(layout, _signed_here(invocation, " ".join(words), statement, params), SIGNED_HERE)
    args = spelling.build(params, None, **filled)
    signed = (SignReviewCommand if command is SignReviewCommand else SignReeCommand).model_validate({"args": args})
    _run_and_finish(invocation, words, signed, layout)


class _Statement(BaseModel):
    """What a signature made here says: about which seal, under which predicate type, with which predicate."""

    ree_name: str
    ree_digest: Digest
    predicate_type: str
    predicate: dict[str, Any] = {}


def _seal_statement(invocation: Invocation, words: str, layout: ReeLayout, params: Params) -> _Statement:
    ree = ReeDirectory(layout).read_ree()
    if ree.seal is None:
        refuse(invocation, words, "precondition", "only a sealed REE is signed: run `ree seal-ree` first")
    claim = params["claim"] or SignReeArgs.model_fields["claim"].default
    return _Statement(
        ree_name=ree.subject.definition.name, ree_digest=ree.seal.ree_digest, predicate_type=PREDICATE_TYPES[claim]
    )


def _review_statement(invocation: Invocation, words: str, layout: ReeLayout, review_id: str) -> _Statement:
    review = layout.review(review_id)
    record = read_review_record(review)
    if record is None:
        refuse(invocation, words, "precondition", f"no review {review_id}")
    if record.subject.ree_digest is None:
        refuse(
            invocation, words, "precondition", f"review {review_id} is of a draft: only a review of a seal is signed"
        )
    return _Statement(
        ree_name=record.subject.name,
        ree_digest=record.subject.ree_digest,
        predicate_type=REVIEW_PREDICATE_TYPE,
        predicate=json.loads(review.metadata.read_bytes()),
    )


def _signed_here(invocation: Invocation, words: str, statement: _Statement, params: Params) -> bytes:
    """A Sigstore bundle of ``statement``, signed under the identity the signer proves now."""
    click.echo(signing.PUBLIC_LOG_NOTICE, err=True)
    request = signing.SigningRequest(
        ree_name=statement.ree_name,
        ree_digest=statement.ree_digest,
        predicate_type=statement.predicate_type,
        predicate=statement.predicate,
        instance="staging" if params["staging"] else "production",
        trust_config=params["trust_config"],
        identity_token=params["identity_token"],
        out_of_band=params["out_of_band"],
    )
    try:
        return signing.sign_seal(request)
    except signing.SigningError as exc:
        refuse(invocation, words, exc.category, str(exc))


def _staged_bytes(layout: ReeLayout, content: bytes, name: str) -> dict[str, str]:
    """Content staged in the REE as a file called ``name``, as the command names it."""
    token = uuid4().hex
    staged = layout.upload_staging_file(token)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(content)
    return {"upload_token": token, "archive_name": name}


def _staged(layout: ReeLayout, archive: Path) -> dict[str, str]:
    """The archive staged in the REE, as the command names it: its upload token and file name."""
    token = uuid4().hex
    staged = layout.upload_staging_file(token)
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(archive, staged)
    return {"upload_token": token, "archive_name": archive.name}


def _script_path(word: str) -> str:
    """A script named by its path in the REE, or by its ``KIND[:EXPERIMENT]``."""
    try:
        return resolve_target(TARGET.convert(word, None, None)).path
    except click.BadParameter:
        return word


def _on_script(
    invocation: Invocation, words: tuple[str, ...], command: type[BaseModel], spelling: Spelling, params: Params
) -> None:
    _run_verb(invocation, words, command, spelling, {**params, "path": _script_path(params["path"])})


def _define(
    invocation: Invocation, words: tuple[str, ...], command: type[BaseModel], spelling: Spelling, params: Params
) -> None:
    layout = _layout_or_refuse(invocation, " ".join(words))
    patch = _definition_patch(layout, params)
    if patch is None:
        _run_verb(invocation, words, command, spelling, params)
        return
    revision = str(revision_of(ReeDirectory(layout).read_ree()))
    args = spelling.build(params, json.dumps(patch).encode(), expected_version=revision)
    _run_and_finish(invocation, words, PatchReeDefinitionCommand.model_validate({"args": args}), layout)


_DEFINE_OPTIONS: list[click.Parameter] = [
    click.Option(["--name"], help="The REE's name."),
    click.Option(["--version", "catalog_version"], help="The REE's version, as its catalog entry gives it."),
    click.Option(["--description"], help="What the REE reproduces, in a sentence."),
    click.Option(["--website"], help="Where the work the REE reproduces is published."),
    click.Option(["--keyword", "keywords"], multiple=True, help="A keyword of the catalog entry; repeated."),
    click.Option(["--artifact-path"], help="Where the build leaves the experiment environment, in the workspace."),
    click.Option(["--launch/--no-launch", "launch"], default=None, help="Run every script through launch.sh, or not."),
    click.Option(
        ["--experiment"], help="Declare, or redeclare, the experiment NAME; a new one starts from default scripts."
    ),
    click.Option(["--output", "outputs"], multiple=True, help="A path the --experiment produces; repeated."),
    click.Option(["--remove-experiment"], multiple=True, help="Remove the experiment NAME from the definition."),
]
_DEFINE_FIELDS = (
    "name",
    "catalog_version",
    "description",
    "website",
    "keywords",
    "artifact_path",
    "launch",
    "experiment",
    "outputs",
    "remove_experiment",
)


def _definition_patch(layout: ReeLayout, params: Params) -> dict[str, Any] | None:
    """The patch the definition options spell, over the definition as it is; None when none is given."""
    if all(params[name] in (None, ()) for name in _DEFINE_FIELDS):
        return None
    if params["outputs"] and not params["experiment"]:
        raise click.UsageError("--output names a path of the --experiment it follows")
    current = ReeDirectory(layout).read_ree().subject.definition
    patch: dict[str, Any] = {}
    if params["name"] is not None:
        patch["name"] = params["name"]
    catalog = {
        "version": params["catalog_version"],
        "description": params["description"],
        "website": params["website"],
        "keywords": list(params["keywords"]) or None,
    }
    if any(value is not None for value in catalog.values()):
        given = {key: value for key, value in catalog.items() if value is not None}
        patch["catalog"] = {**current.catalog.model_dump(mode="json"), **given}
    if params["artifact_path"] is not None:
        patch["experiment_environment"] = {"artifact_path": params["artifact_path"]}
    if params["launch"] is not None:
        patch["launch"] = {} if params["launch"] else None
    if params["experiment"] or params["remove_experiment"]:
        removed = {params["experiment"], *params["remove_experiment"]}
        experiments = [
            {"name": item.name, "output_paths": [str(path) for path in item.output_paths]}
            for item in current.experiments
            if item.name not in removed
        ]
        if params["experiment"]:
            experiments.append({"name": params["experiment"], "output_paths": list(params["outputs"])})
        patch["experiments"] = experiments
    return patch


def _infer(
    invocation: Invocation, words: tuple[str, ...], command: type[BaseModel], spelling: Spelling, params: Params
) -> None:
    joined = " ".join(words)
    layout = _layout_or_refuse(invocation, joined)
    if params["write"] and len(params["targets"]) != 1:
        raise click.UsageError("--write writes one script: give one --target")
    if params["rule"] and not params["write"]:
        raise click.UsageError("--rule picks the proposal --write writes")
    if not params["targets"]:
        params = {**params, "targets": _every_target(layout)}
    args = spelling.build(params, None)
    infer = SuggestScriptsCommand.model_validate({"args": args})
    inferred = invocation.run(infer, layout, identity=invocation.identity(1) if params["write"] else None)

    def shown(outputs: dict[str, Any]) -> str:
        report = InferenceReport.model_validate(outputs)
        return render.inference(
            report, {item.target.path: _overlay_text(layout, item.target.path) for item in report.results}
        )

    if not params["write"] or inferred.status != "succeeded":
        finish(invocation, joined, inferred, render_with=shown)
    [result] = InferenceReport.model_validate(inferred.outputs).results
    proposals = [
        candidate
        for candidate in result.candidates
        if candidate.body is not None and params["rule"] in (None, candidate.inference_rule)
    ]
    if not proposals:
        if not invocation.machine:
            click.echo(shown(inferred.outputs))
        rule = f" by rule {params['rule']}" if params["rule"] else ""
        refuse(invocation, joined, "precondition", f"inference proposes no script for {result.target.path}{rule}")
    chosen = proposals[0]
    content = cast(str, chosen.body)
    write = WriteScriptCommand(args=WriteScriptArgs(path=chosen.target.path, content=content))
    written = invocation.run(write, layout, identity=invocation.identity(2))
    if written.status != "succeeded":
        finish(invocation, joined, written, ran=True)
    outputs = ScriptWritten(path=chosen.target.path, rule=chosen.inference_rule, candidate_id=chosen.candidate_id)
    finish(
        invocation,
        joined,
        written.model_copy(update={"outputs": outputs.model_dump(mode="json")}),
        render_with=lambda _outputs: f"wrote {outputs.path} as rule {outputs.rule} proposes it",
        ran=True,
    )


def _every_target(layout: ReeLayout) -> tuple[ScriptTargetSelectorArg, ...]:
    """Every script of the REE: each kind, and each declared experiment's run and verify scripts."""
    experiments = [item.name for item in ReeDirectory(layout).read_ree().subject.definition.experiments]
    return tuple(
        ScriptTargetSelectorArg.model_validate({"kind": kind, "experiment_name": name})
        for kind in KINDS
        for name in (experiments if kind in EXPERIMENT_KINDS else [None])
    )


def _overlay_text(layout: ReeLayout, path: str) -> str | None:
    file = layout.overlay_file(path)
    try:
        return file.read_text(encoding="utf-8") if file.is_file() else None
    except UnicodeDecodeError:
        return None


def _seal(
    invocation: Invocation, words: tuple[str, ...], command: type[BaseModel], spelling: Spelling, params: Params
) -> None:
    layout = _layout_or_refuse(invocation, " ".join(words))
    if not _sealing_confirmed(invocation, layout):
        raise click.Abort
    _run_verb(invocation, words, command, spelling, params)


def _at_terminal() -> bool:
    return sys.stdin.isatty()


def _sealing_confirmed(invocation: Invocation, layout: ReeLayout) -> bool:
    """A person at a terminal confirms a seal, which no command undoes, seeing which steps are not complete."""
    if invocation.machine or not _at_terminal():
        return True
    steps = get_ree_steps(layout).steps
    open_steps = [step.label for step in steps if step.key != "seal_ree" and step.status != "complete"]
    if open_steps:
        click.echo(f"Not complete: {', '.join(open_steps)}.", err=True)
    return click.confirm("Sealing freezes this REE: it takes no edit after it. Seal it?", err=True)


def _new_review_id() -> str:
    return f"review-{uuid4().hex[:12]}"


def _newest_review(invocation: Invocation, words: str, layout: ReeLayout) -> str:
    reviews = load_reviews(layout).reviews
    if not reviews:
        refuse(invocation, words, "precondition", "no review yet: open one with `ree review acquire-source`")
    return reviews[0].review_id


def _review_step(
    invocation: Invocation, words: tuple[str, ...], command: type[BaseModel], spelling: Spelling, params: Params
) -> None:
    layout = _layout_or_refuse(invocation, " ".join(words))
    if params["review_id"] is None:
        opening = command is ReviewAcquireSourceCommand
        params = {
            **params,
            "review_id": _new_review_id() if opening else _newest_review(invocation, " ".join(words), layout),
        }
    _run_verb(invocation, words, command, spelling, params)


_HANDLERS: dict[type[BaseModel], Handler] = {
    AcquireSourceCommand: _acquire_source,
    LoadReeBundleCommand: _load_bundle,
    WriteScriptCommand: _on_script,
    PatchReeDefinitionCommand: _define,
    SuggestScriptsCommand: _infer,
    SealReeCommand: _seal,
    SignReeCommand: _sign,
    SignReviewCommand: _sign,
    ReviewAcquireSourceCommand: _review_step,
    ReviewBuildExperimentEnvironmentCommand: _review_step,
    ReviewActivateExperimentEnvironmentCommand: _review_step,
    ReviewRunExperimentCommand: _review_step,
}
_REVIEW_ID = ("review_id",)
# Required fields the command line fills when they are not given.
_OPTIONAL: dict[type[BaseModel], tuple[str, ...]] = {
    AcquireSourceCommand: ("mode",),
    LoadReeBundleCommand: ("upload_token", "archive_name"),
    SignReeCommand: ("upload_token", "archive_name"),
    SignReviewCommand: ("upload_token", "archive_name"),
    ReviewAcquireSourceCommand: _REVIEW_ID,
    ReviewBuildExperimentEnvironmentCommand: _REVIEW_ID,
    ReviewActivateExperimentEnvironmentCommand: _REVIEW_ID,
    ReviewRunExperimentCommand: _REVIEW_ID,
}
# Fields a workbench passes and a person does not.
_STAGED = ("upload_token", "archive_name")
_HIDDEN: dict[type[BaseModel], tuple[str, ...]] = {
    AcquireSourceCommand: _STAGED,
    LoadReeBundleCommand: _STAGED,
    SignReeCommand: _STAGED,
    SignReviewCommand: _STAGED,
}
_ARCHIVE = click.Option(
    [ARCHIVE_OPTION, "archive"],
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
    help="The archive to take, staged in the REE.",
)
# How a signature is made here, for the seal and for a review of it alike.
_SIGNING: list[click.Parameter] = [
    click.Option(
        [BUNDLE_OPTION, "bundle"],
        type=click.Path(dir_okay=False, exists=True, path_type=Path),
        help="A Sigstore bundle signed elsewhere, to add instead of signing here.",
    ),
    click.Option(
        ["--identity-token", "identity_token"],
        envvar="SIGSTORE_IDENTITY_TOKEN",
        default=None,
        help="An OIDC token to sign under, in place of signing in; read from SIGSTORE_IDENTITY_TOKEN.",
    ),
    click.Option(
        ["--out-of-band", "out_of_band"],
        is_flag=True,
        help="Sign in by pasting a code from the browser, where no browser can reach this machine.",
    ),
    click.Option(["--staging"], is_flag=True, help="Sign with Sigstore's staging instance, for trying it out."),
    click.Option(
        ["--trust-config", "trust_config"],
        type=click.Path(dir_okay=False, exists=True, path_type=Path),
        default=None,
        help="A Sigstore client trust configuration naming other services, such as a local stack.",
    ),
]
_EXTRA: dict[type[BaseModel], list[click.Parameter]] = {
    AcquireSourceCommand: [_ARCHIVE],
    LoadReeBundleCommand: [_ARCHIVE],
    SignReeCommand: _SIGNING,
    SignReviewCommand: _SIGNING,
    PatchReeDefinitionCommand: _DEFINE_OPTIONS,
    SuggestScriptsCommand: [
        click.Option(["--write"], is_flag=True, help="Write the proposed script, for one --target."),
        click.Option(["--rule"], default=None, help="With --write, the rule whose proposal to write."),
    ],
}
# What a command's help adds to its summary.
_MORE: dict[type[BaseModel], str] = {
    WriteScriptCommand: "The script is read on stdin: `ree write-script build_experiment_environment < build.sh`.",
    PatchReeDefinitionCommand: (
        "Give the options for the common fields, or pipe a JSON patch of the definition's top-level fields on stdin."
    ),
    SuggestScriptsCommand: (
        "Shows each proposal against the script as it is written. Without --target, proposes every script."
    ),
    SignReeCommand: (
        "Signs the seal's digest with Sigstore: you sign in with your OIDC identity (a browser opens, or use "
        "--out-of-band), and your identity is logged publicly in Sigstore's transparency log. A CI job's own token "
        "is used where there is one. With --bundle, adds a bundle signed elsewhere instead. The REE keeps the "
        "signature beside what the seal covers."
    ),
    SignReviewCommand: (
        "Signs the review with Sigstore, as sign-ree signs the seal: the signed statement names the reviewed seal "
        "and carries the review's record, so the one bundle is the review, signed, for anyone to check. Only a "
        "review of a sealed REE that is not running is signed, and a signed review changes no more."
    ),
}


def _verb_command(command: type[BaseModel], words: tuple[str, ...]) -> click.Command:
    spelling = Spelling(_args_of(command), optional=_OPTIONAL.get(command, ()), hidden=_HIDDEN.get(command, ()))
    handler = _HANDLERS.get(command, _run_verb)

    def callback(**params: Any) -> None:
        handler(_invocation(), words, command, spelling, params)

    operation = str(command.model_fields["operation"].default)
    summary = SUMMARIES[command]
    return ReeCommand(
        words[-1],
        callback=callback,
        params=[*_EXTRA.get(command, []), *spelling.params],
        help=f"{summary}.\n\n{_MORE[command]}" if command in _MORE else summary,
        short_help=summary,
        words=words,
        outputs=OUTPUTS[operation] | ScriptWritten if command is SuggestScriptsCommand else OUTPUTS[operation],
        spelling=spelling,
        runs=True,
        operations=(operation, "write_script") if command is SuggestScriptsCommand else (operation,),
    )


for _command, _words in VERBS.items():
    (review if _words[0] == REVIEW else cli).add_command(_verb_command(_command, _words))


@review.command(
    "all",
    cls=ReeCommand,
    words=(REVIEW, "all"),
    outputs=ReviewRun,
    runs=True,
    operations=(
        "review_acquire_source",
        "review_build_experiment_environment",
        "review_activate_experiment_environment",
        "review_run_experiment",
    ),
    params=Spelling(ReviewAcquireSourceArgs, optional=_REVIEW_ID).params,
)
def review_all(**params: Any) -> None:
    """Review every step: the source, the experiment environment, the activation and each experiment.

    Stops at the first step that does not succeed. --basis applies to the source and the build.
    """
    invocation = _invocation()
    words = "review all"
    layout = _layout_or_refuse(invocation, words)
    opened = cast(
        ReviewAcquireSourceArgs,
        Spelling(ReviewAcquireSourceArgs, optional=_REVIEW_ID).build(params, None, review_id=_new_review_id()),
    )
    review_id = opened.review_id
    experiments = [item.name for item in ReeDirectory(layout).read_ree().subject.definition.experiments]
    commands: list[tuple[list[str], Command]] = [
        ([*VERBS[ReviewAcquireSourceCommand]], ReviewAcquireSourceCommand(args=opened)),
        (
            [*VERBS[ReviewBuildExperimentEnvironmentCommand]],
            ReviewBuildExperimentEnvironmentCommand.model_validate(
                {"args": {"review_id": review_id, "basis": opened.basis}}
            ),
        ),
        (
            [*VERBS[ReviewActivateExperimentEnvironmentCommand]],
            ReviewActivateExperimentEnvironmentCommand.model_validate({"args": {"review_id": review_id}}),
        ),
        *(
            (
                [*VERBS[ReviewRunExperimentCommand], name],
                ReviewRunExperimentCommand.model_validate({"args": {"review_id": review_id, "experiment_name": name}}),
            )
            for name in experiments
        ),
    ]
    steps: list[StepRun] = []
    last = ActionResult(status="succeeded")
    for number, (step_words, cmd) in enumerate(commands, start=1):
        if not invocation.machine:
            click.echo(click.style(f"ree {' '.join(step_words)}", bold=True), err=True)
        identity = invocation.identity(number)
        last = invocation.run(cmd, layout, identity=identity)
        run_id = identity[1]
        steps.append(StepRun(words=step_words, run_id=run_id, status=last.status))
        if last.status != "succeeded":
            break
    record = next((item for item in load_reviews(layout).reviews if item.review_id == review_id), None)
    outputs = ReviewRun(review_id=review_id, steps=steps, review=record)
    finish(
        invocation,
        words,
        last.model_copy(update={"outputs": outputs.model_dump(mode="json")}),
        render_with=lambda _outputs: render.review(record) if record else review_id,
        ran=True,
    )


# ================================================
# Reads, and init
# ================================================


def _read_command(
    model: type[BaseModel],
    answer_read: Callable[[Invocation, BaseModel], None],
    *,
    hidden: bool = False,
    optional: tuple[str, ...] = (),
) -> click.Command:
    spelling = Spelling(model, optional=optional)

    def callback(**params: Any) -> None:
        invocation = _invocation()
        stdin = read_stdin(model)
        answer_read(invocation, spelling.build(params, stdin, **_filled(model, invocation)))

    summary = (model.__doc__ or "").strip()
    return ReeCommand(
        verb_of(model),
        callback=callback,
        params=spelling.params,
        help=summary,
        short_help=summary.split("\n")[0],
        hidden=hidden,
        words=(verb_of(model),),
        outputs=REPLIES.get(model, Initialized if model is InitRee else None),
        spelling=spelling,
        stdout="bytes" if model in (CatQuery, BundleQuery) else "result",
        operations=("initialize_ree",) if model is InitRee else (),
    )


def _filled(model: type[BaseModel], invocation: Invocation) -> dict[str, Any]:
    if model is InitRee:
        return {"name": (invocation.ree or Path.cwd()).name}
    return {}


def _init(invocation: Invocation, read: BaseModel) -> None:
    root = invocation.ree or Path.cwd()
    try:
        result = initialize_ree(ReeLayout(root=root), name=cast(InitRee, read).name)
    except HistoryCaptureError as exc:
        refuse(invocation, verb_of(InitRee), "precondition", str(exc))
    initialized = Initialized(root=str(root), state=result.status, snapshot_id=result.snapshot_id)
    answer(
        invocation,
        verb_of(InitRee),
        initialized,
        render_with=lambda _outputs: f"{result.status.replace('_', ' ')} {root}\nnext: ree status",
    )


def _reading(
    words: str,
    read: Callable[[ReeLayout, BaseModel], BaseModel | dict[str, Any]],
    render_with: Callable[[dict[str, Any]], str] | None = None,
) -> Callable[[Invocation, BaseModel], None]:
    """Answer a read of the REE with what ``read`` finds, rendered for a person by ``render_with``."""

    def answer_read(invocation: Invocation, query: BaseModel) -> None:
        layout = _layout_or_refuse(invocation, words)
        try:
            found = read(layout, query)
        except FileNotFoundError as exc:
            refuse(invocation, words, "precondition", str(exc))
        answer(invocation, words, found, render_with=render_with)

    return answer_read


def _bytes(words: str, write: Callable[[ReeLayout, BaseModel], None]) -> Callable[[Invocation, BaseModel], None]:
    """Answer a read whose answer is bytes on stdout; a refusal is a result, as any other."""

    def answer_read(invocation: Invocation, query: BaseModel) -> None:
        layout = _layout_or_refuse(invocation, words)
        try:
            write(layout, query)
        except FileNotFoundError as exc:
            refuse(invocation, words, "validation", f"not found: {exc}")
        except (ValueError, RuntimeError) as exc:
            refuse(invocation, words, "validation", str(exc))

    return answer_read


def _write_bundle(layout: ReeLayout, _query: BaseModel) -> None:
    with materialized_ree_download(layout) as path, path.open("rb") as archive:
        shutil.copyfileobj(archive, sys.stdout.buffer, length=1024 * 1024)


def _write_file(layout: ReeLayout, query: BaseModel) -> None:
    path = cast(CatQuery, query).path
    try:
        data = read_ree_file_bytes(layout, path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(path) from exc
    sys.stdout.buffer.write(data)


def _lint_draft(invocation: Invocation, read: BaseModel) -> None:
    query = cast(LintDraftQuery, read)
    report = lint_script(
        resolve_target(query.target), query.source, declarations=query.declarations, tiers=CONTRACT_ONLY
    )
    answer(invocation, "lint-draft", report)


def _templates(invocation: Invocation, _read: BaseModel) -> None:
    catalog = script_template_catalog()
    answer(
        invocation,
        "templates",
        catalog,
        render_with=lambda outputs: render.templates(type(catalog).model_validate(outputs)),
    )


_READS: list[click.Command] = [
    _read_command(InitRee, _init, optional=("name",)),
    _read_command(
        ShowQuery,
        _reading(
            "show",
            lambda layout, query: get_ree_document(layout, include_content=not cast(ShowQuery, query).summary),
            lambda outputs: render.document(WorkbenchReeDocument.model_validate(outputs)),
        ),
    ),
    _read_command(
        ReviewsQuery,
        _reading(
            "reviews",
            lambda layout, _query: load_reviews(layout),
            lambda outputs: render.reviews(ReviewSet.model_validate(outputs)),
        ),
    ),
    _read_command(
        LogQuery,
        _reading(
            "log",
            lambda layout, _query: read_operation_history(layout),
            lambda outputs: render.history(OperationHistory.model_validate(outputs)),
        ),
    ),
    _read_command(
        ManifestQuery,
        _reading("manifest", lambda layout, _query: ReeDirectory(layout).read_manifest_json()),
        hidden=True,
    ),
    _read_command(CatQuery, _bytes("cat", _write_file)),
    _read_command(BundleQuery, _bytes("bundle", _write_bundle)),
    _read_command(TemplatesQuery, _templates),
    _read_command(LintDraftQuery, _lint_draft, hidden=True),
]
for _read in _READS:
    cli.add_command(_read)


# ================================================
# Authoring
# ================================================


@cli.command("status", cls=ReeCommand, words=("status",), outputs=ReeStatusReport)
def status_cmd() -> None:
    """Show where the REE stands: each step, its evidence, and what to run next."""
    invocation = _invocation()
    layout = _layout_or_refuse(invocation, "status")
    report = get_ree_status(layout)
    answer(
        invocation, "status", report, render_with=lambda outputs: render.status(type(report).model_validate(outputs))
    )


@cli.command("verify-signatures", cls=ReeCommand, words=("verify-signatures",), outputs=SignatureVerifications)
@click.option("--review-id", default=None, help="Verify this review's signature, not the REE's own.")
@click.option(
    "--policy",
    "policy_file",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
    default=None,
    help="A verification policy (JSON): the trust root, and whose signature counts for each claim.",
)
@click.option("--identity", default=None, help="The one signer whose signature counts, for every claim; with --issuer.")
@click.option("--issuer", default=None, help="The OIDC issuer that proves --identity.")
@click.option("--staging", is_flag=True, help="Hold signatures to Sigstore's staging instance's trust root.")
@click.option(
    "--trust-config",
    "trust_config",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
    default=None,
    help="A Sigstore client trust configuration naming another trust root, such as a local stack's.",
)
def verify_signatures_cmd(
    review_id: str | None,
    policy_file: Path | None,
    identity: str | None,
    issuer: str | None,
    staging: bool,
    trust_config: Path | None,
) -> None:
    """Verify the sealed REE's signatures, or a review's, with Sigstore, under a policy of whose signature counts.

    Each signature is held to what the REE says of it (the seal it names, its claim, a review's record), then to
    Sigstore (the chain to the trust root, the transparency log, the key that signed), then to the policy. Nothing is
    written. Every signature is reported; the command fails unless there is one and each is verified.
    """
    invocation = _invocation()
    words = "verify-signatures"
    layout = _layout_or_refuse(invocation, words)
    if policy_file is not None and (identity or issuer):
        refuse(invocation, words, "validation", "give a --policy, or one --identity with its --issuer, not both")
    if (identity is None) != (issuer is None):
        refuse(invocation, words, "validation", "give --identity with the --issuer that proves it")
    if policy_file is not None:
        policy = VerificationPolicy.model_validate_json(policy_file.read_text(encoding="utf-8"))
    else:
        signer = (Signer(identity=identity, issuer=issuer),) if identity and issuer else ()
        policy = VerificationPolicy(signers=dict.fromkeys(("author_approval", "review"), signer) if signer else {})
    if staging:
        policy = policy.model_copy(update={"trust": "staging"})
    record: JsonValue | None = None
    if review_id is not None:
        review = layout.review(review_id)
        reviewed = read_review_record(review)
        if reviewed is None:
            refuse(invocation, words, "precondition", f"no review {review_id}")
        if reviewed.subject.ree_digest is None:
            refuse(invocation, words, "precondition", f"review {review_id} is of a draft, which no one signs")
        seal = reviewed.subject.ree_digest
        record = json.loads(review.metadata.read_bytes())
        claim: VerifiedClaim = "review"
        found: list[tuple[str, Path, VerifiedClaim | None]] = [
            (review_signature_path(), review.root / review_signature_path(), claim)
        ]
    else:
        sealed = ReeDirectory(layout).read_ree().seal
        if sealed is None:
            refuse(invocation, words, "precondition", "only a sealed REE is signed: run `ree seal-ree` first")
        seal = sealed.ree_digest
        found = [
            (path.relative_to(layout.root).as_posix(), path, _claim_named(path.name))
            for path in sorted((layout.root / SIGNATURES).glob(f"*{SIGNATURE_SUFFIX}"))
        ]
    try:
        verified = tuple(
            signing.verify_signature(
                path.read_bytes(),
                path=name,
                claim=claim,
                seal=seal,
                record=record,
                policy=policy,
                trust_config=trust_config,
            )
            for name, path, claim in found
            if path.is_file()
        )
    except ModuleNotFoundError:
        refuse(invocation, words, "precondition", "this ree has no Sigstore client to verify with")
    report = SignatureVerifications(ree_digest=seal, review_id=review_id, policy=policy, signatures=verified)
    outputs = report.model_dump(mode="json")
    unverified = [item for item in verified if item.outcome != "verified"]
    if not verified or unverified:
        message = (
            "nothing here is signed"
            if not verified
            else "; ".join(f"{item.path} is {item.outcome}: {item.reason}" for item in unverified)
        )
        finish(invocation, words, ActionResult.failed("validation", message, origin="executor", outputs=outputs))
    answer(invocation, words, report, render_with=lambda _outputs: render.verifications(report))


def _claim_named(name: str) -> VerifiedClaim | None:
    """The claim a signature of the REE is named for; None for a file named for none."""
    claim = name.removesuffix(SIGNATURE_SUFFIX)
    return "author_approval" if claim == "author_approval" else None


@cli.command("edit", cls=ReeCommand, words=("edit",), outputs=ScriptEdited, runs=True, operations=("write_script",))
@click.argument("script", type=TARGET)
def edit_cmd(script: ScriptTargetSelectorArg) -> None:
    """Edit one of the REE's scripts, SCRIPT as KIND[:EXPERIMENT], in $VISUAL or $EDITOR, and write it.

    A script not written yet starts from its default template. The edit is written only if the script did not change
    meanwhile.
    """
    invocation = _invocation()
    layout = _layout_or_refuse(invocation, "edit")
    if invocation.machine or not _at_terminal():
        refuse(invocation, "edit", "validation", "edit needs a terminal: write a script with `ree write-script`")
    store = ReeDirectory(layout)
    if store.read_ree().seal is not None:
        refuse(invocation, "edit", "precondition", "a sealed REE takes no edits")
    path = resolve_target(script).path
    before = _overlay_text(layout, path)
    edited = click.edit(before if before is not None else _template(script.kind), extension=".sh", require_save=True)
    if edited is None or edited == before:
        answer(
            invocation, "edit", ScriptEdited(path=path, changed=False), render_with=lambda _outputs: f"{path} unchanged"
        )
    etag = workspace_content_etag(store, path) or ""
    write = WriteScriptCommand(args=WriteScriptArgs(path=path, content=edited, expected_etag=etag))
    written = invocation.run(write, layout)
    outputs = ScriptEdited(path=path, changed=True).model_dump(mode="json")
    finish(
        invocation,
        "edit",
        written.model_copy(update={"outputs": outputs}) if written.status == "succeeded" else written,
        render_with=lambda _outputs: f"wrote {path}",
        ran=True,
    )


def _template(kind: TargetKind) -> str:
    entries = script_template_catalog().of(kind).templates
    return next((entry.body for entry in entries if entry.is_default), entries[0].body if entries else "")


# ================================================
# Runs
# ================================================


@cli.command("wait", cls=ReeCommand, words=("wait",), outputs=Waited)
@click.option("--timeout", type=float, default=None, help="Give up after this many seconds.")
def wait_cmd(timeout: float | None) -> None:
    """Wait until no command runs in the REE."""
    invocation = _invocation()
    layout = _layout_or_refuse(invocation, "wait")
    try:
        held_by = wait_until_free(layout, timeout=timeout)
    except TimeoutError as exc:
        refuse(invocation, "wait", "timeout", str(exc))
    answer(
        invocation,
        "wait",
        Waited(held_by=held_by),
        render_with=lambda _outputs: f"run {held_by} ended" if held_by else "no command was running",
    )


@cli.command("cancel", cls=ReeCommand, words=("cancel",), outputs=CancelRequested)
@click.argument("run_id", required=False)
def cancel_cmd(run_id: str | None) -> None:
    """Ask the run RUN_ID, by default the one running, to stop: it rolls the REE back and is captured as canceled."""
    invocation = _invocation()
    layout = _layout_or_refuse(invocation, "cancel")
    run_id = run_id or running_run(layout)
    if run_id is None:
        refuse(invocation, "cancel", "precondition", "no command is running in this REE")
    request_cancel(layout, run_id)
    answer(
        invocation, "cancel", CancelRequested(run_id=run_id), render_with=lambda _outputs: f"asked run {run_id} to stop"
    )


@cli.command("settle", hidden=True)
@click.argument("attempt_id")
@click.option("--command", "command_file", type=Path, default=None, help="The command it was started with, as JSON.")
def settle_cmd(attempt_id: str, command_file: Path | None) -> None:
    """Settle ATTEMPT_ID, whose process ended without reporting, and print how it ended.

    With its command, an attempt never recorded is recorded as having begun nothing. Prints nothing when the REE
    holds no such attempt and no command is given.
    """
    invocation = _invocation()
    try:
        layout = invocation.layout()
    except NoReeError as exc:
        click.echo(str(exc), err=True)
        sys.exit(FAILED)
    cmd = command_adapter.validate_json(command_file.read_text(encoding="utf-8")) if command_file else None
    result = settle_interrupted(
        layout=layout,
        attempt_id=attempt_id,
        log=invocation.sink(),
        cmd=cmd,
        run_id=invocation.run_id,
        context=invocation.context,
    )
    if result is not None:
        click.echo(result.model_dump_json())


# ================================================
# This machine, and ree itself
# ================================================


@cli.command("build-info", hidden=True)
def build_info_cmd() -> None:
    """Print this command line's build identity."""
    answer(_invocation(), "build-info", current_build("repo2ree-cli"))


@cli.command("machine", cls=ReeCommand, words=("machine",), outputs=MachineFacts)
def machine_cmd() -> None:
    """Print the machine ree runs an REE's scripts on: its architecture and GPUs, and whether it is a container."""
    answer(_invocation(), "machine", machine_facts())


@cli.command("schema", cls=ReeCommand, words=("schema",), stdout="schema")
@click.argument("words", nargs=-1)
def schema_cmd(words: tuple[str, ...]) -> None:
    """Describe every command, or the one WORDS names, as data: its arguments, its stdin and its outputs.

    What an agent reads to learn ree; the exit statuses and failure categories come with it.
    """
    invocation = _invocation()
    try:
        described = describe(cli, words, EXIT_CODES, REE_STEPS)
    except LookupError as exc:
        refuse(invocation, "schema", "validation", str(exc))
    click.echo(json.dumps(described, indent=None if invocation.machine else 2))


@cli.command("completion", cls=ReeCommand, words=("completion",), stdout="script")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion_cmd(shell: str) -> None:
    """Print the completion script for SHELL: `eval "$(ree completion bash)"`."""
    completion = get_completion_class(shell)
    if completion is None:
        raise click.UsageError(f"no completion for {shell}")
    click.echo(completion(cli, {}, "ree", "_REE_COMPLETE").source())


def read_back(argv: list[str], stdin: bytes | None = None) -> BaseModel:
    """The command or read an argv after ``ree`` spells, as ``ree`` parses it: the inverse of ``to_argv``."""
    context = click.Context(cli)
    command: click.Command = cli
    rest = list(argv)
    name = "ree"
    while isinstance(command, click.Group):
        found, sub, rest = command.resolve_command(context, rest)
        if sub is None or found is None:
            raise click.UsageError(f"no command {argv!r}")
        name, command = found, sub
    spelling = cast(ReeCommand, command).spelling
    if spelling is None:
        raise click.UsageError(f"{name} spells no command")
    args = spelling.build(command.make_context(name, rest, parent=context).params, stdin)
    words = cast(ReeCommand, command).words
    verb = next((command_type for command_type, spelled in VERBS.items() if spelled == words), None)
    return args if verb is None else verb.model_validate({"args": args})


__all__ = ["cli", "main", "nearest_ree", "read_back"]

"""Apply a top-level definition patch directly to the portable REE."""

from __future__ import annotations

from repo2ree_core.domain.ree.transitions import ReePreconditionError, replace_definition, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.handlers.author.definition_authoring import patched_definition
from repo2ree_core.operations.handlers.author.file_concurrency import VersionConflictOutputs
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_protocol.command import PatchReeDefinitionArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_patch_ree_definition(
    args: PatchReeDefinitionArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)
    if not store.record_exists():
        return ActionResult.failed("precondition", "metadata not found — was init-ree run?")
    try:
        ree = load_ree(layout, store)
        before_revision = revision_of(ree)
        if args.expected_version and args.expected_version != before_revision:
            return ActionResult.failed(
                "conflict",
                "REE definition changed since it was read",
                retryable=True,
                outputs=VersionConflictOutputs(
                    expected_version=args.expected_version,
                    actual_version=before_revision,
                ).as_outputs(),
            )
        definition = patched_definition(ree.subject.definition, args.patch, layout)
        updated = replace_definition(ree, definition)
    except ReePreconditionError as exc:
        return ActionResult.failed("precondition", str(exc))
    except ValueError as exc:
        return ActionResult.failed("validation", str(exc))
    except Exception as exc:
        return failed_from_exception(exc, f"failed to prepare definition patch: {exc}")
    if is_canceled():
        return ActionResult(status="canceled")
    try:
        save_ree(layout, store, updated, expected_revision=before_revision)
    except ReeRevisionConflictError as exc:
        return ActionResult.failed("conflict", str(exc), retryable=True)
    except Exception as exc:
        return failed_from_exception(exc, f"failed to persist definition patch: {exc}")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs={"revision": str(revision_of(updated)), "definition": definition.model_dump(mode="json")},
    )

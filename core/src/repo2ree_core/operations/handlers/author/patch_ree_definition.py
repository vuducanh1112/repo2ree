"""Apply a top-level definition patch directly to the portable REE, with the scripts its experiments bring and take."""

from __future__ import annotations

from repo2ree_core.domain.ree.transitions import ReePreconditionError, replace_definition, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.handlers.author.definition_authoring import (
    ExperimentScripts,
    experiment_scripts,
    patched_definition,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_protocol.command import PatchReeDefinitionArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import PatchReeDefinitionOutputs, VersionConflictOutputs
from repo2ree_protocol.result import ActionResult


def handle_patch_ree_definition(
    args: PatchReeDefinitionArgs,
    *,
    layout: ReeLayout,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "no REE here: run `ree initialize-ree` first")
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
        if ree.seal is not None:
            raise ReePreconditionError("a sealed REE cannot be authored")
        scripts = experiment_scripts(ree.subject.definition, args.patch, layout)
    except ReePreconditionError as exc:
        return ActionResult.failed("precondition", str(exc))
    except (TypeError, ValueError) as exc:
        return ActionResult.failed("validation", str(exc))
    except Exception as exc:
        return failed_from_exception(exc, f"failed to prepare definition patch: {exc}")
    if is_canceled():
        return ActionResult(status="canceled")
    previous = {path: store.overlay.read_bytes(path) for path in scripts.removed}
    try:
        _apply(store, scripts)
        definition = patched_definition(ree.subject.definition, args.patch, layout)
        updated = replace_definition(ree, definition)
        save_ree(layout, store, updated, expected_revision=before_revision)
    except ReeRevisionConflictError as exc:
        _restore(store, scripts, previous)
        return ActionResult.failed("conflict", str(exc), retryable=True)
    except ReePreconditionError as exc:
        _restore(store, scripts, previous)
        return ActionResult.failed("precondition", str(exc))
    except ValueError as exc:
        _restore(store, scripts, previous)
        return ActionResult.failed("validation", str(exc))
    except Exception as exc:
        _restore(store, scripts, previous)
        return failed_from_exception(exc, f"failed to apply definition patch: {exc}")
    for source, target in scripts.moved.items():
        log("system", "info", f"moved {source} to {target} with its experiment")
    for path in scripts.seeded:
        log("system", "info", f"declared {path}, as its default")
    for path in scripts.removed:
        log("system", "info", f"removed {path} with its experiment")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=PatchReeDefinitionOutputs(revision=str(revision_of(updated)), definition=definition).model_dump(
            mode="json"
        ),
    )


def _apply(store: ReeDirectory, scripts: ExperimentScripts) -> None:
    for source, target in scripts.moved.items():
        _move(store, source, target)
    for path, content in scripts.seeded.items():
        store.overlay.write_text(path, content)
        store.workspace.write_text(path, content)
    for path in scripts.removed:
        store.overlay.delete_if_exists(path)
        store.workspace.delete_if_exists(path)


def _restore(store: ReeDirectory, scripts: ExperimentScripts, previous: dict[str, bytes]) -> None:
    for path in scripts.seeded:
        store.overlay.delete_if_exists(path)
        store.workspace.delete_if_exists(path)
    for source, target in scripts.moved.items():
        if store.overlay.is_file(target):
            _move(store, target, source)
    for path, content in previous.items():
        store.overlay.write_bytes(path, content)
        store.workspace.write_bytes(path, content)


def _move(store: ReeDirectory, source: str, target: str) -> None:
    content = store.overlay.read_bytes(source)
    store.overlay.write_bytes(target, content)
    store.workspace.write_bytes(target, content)
    store.overlay.delete_if_exists(source)
    store.workspace.delete_if_exists(source)

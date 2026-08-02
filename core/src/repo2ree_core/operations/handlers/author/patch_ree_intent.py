"""Handler for the patch_ree_intent operation.

Applies a partial patch to reeIntent in /ree/.ree.json.
All ReeIntent fields are user-editable; no whitelist needed.
"""

from __future__ import annotations

from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.steps.author import (
    VersionConflictOutputs,
    open_ree_store,
    patch_ree_intent,
)
from repo2ree_core.persistence.receipts import prune_author_experiment_receipts
from repo2ree_protocol.command import PatchReeIntentArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

_INTENT_FIELDS: frozenset[str] = frozenset(ReeIntent.model_fields)


def handle_patch_ree_intent(
    args: PatchReeIntentArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    unsupported = sorted(set(args.patch) - _INTENT_FIELDS)
    if unsupported:
        log("system", "error", f"patch contains unknown fields: {unsupported}")
        return ActionResult.failed(
            "validation",
            f"patch contains unknown fields: {unsupported}",
            details={"fields": unsupported},
        )

    opened = open_ree_store(log)
    if isinstance(opened, ActionResult):
        return opened
    layout, store = opened

    if args.expected_version:
        actual_version = store.read_record().updated_at
        if args.expected_version != actual_version:
            log(
                "system",
                "error",
                f"intent version mismatch: expected {args.expected_version}, actual {actual_version}",
            )
            return ActionResult.failed(
                "conflict",
                "REE intent changed since it was read",
                retryable=True,
                # The intent is versioned by the record's updated_at rather
                # than by a file etag, so the conflict names no path — but it
                # is the same conflict, reported in the same shape.
                outputs=VersionConflictOutputs(
                    expected_version=args.expected_version,
                    actual_version=actual_version,
                ).as_outputs(),
            )

    log("system", "info", f"patch_ree_intent: {sorted(args.patch)}")
    try:
        patch_ree_intent(store, args.patch)
        prune_author_experiment_receipts(layout, store.read_intent())
    except Exception as exc:
        log("system", "error", f"patch_ree_intent failed: {exc}")
        return failed_from_exception(exc, f"patch_ree_intent failed: {exc}")

    return ActionResult(status="succeeded", exit_code=0)
